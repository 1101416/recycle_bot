import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, optimizers, callbacks
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import logging
from datetime import datetime
import json
from config import Config

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WasteClassificationTrainer:
    def __init__(self, data_dir='data/training', model_dir='models'):
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.class_names = list(Config.WASTE_CATEGORIES.keys())
        self.num_classes = len(self.class_names)
        self.image_size = Config.IMAGE_SIZE
        
        # 建立目錄
        os.makedirs(self.model_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 初始化模型
        self.model = None
        self.history = None
    
    def prepare_data(self, validation_split=0.2, test_split=0.1):
        """準備訓練資料"""
        logger.info("準備訓練資料...")
        
        # 使用 ImageDataGenerator 進行資料增強
        train_datagen = ImageDataGenerator(
            rescale=1./255,
            rotation_range=20,
            width_shift_range=0.2,
            height_shift_range=0.2,
            horizontal_flip=True,
            zoom_range=0.2,
            shear_range=0.2,
            fill_mode='nearest',
            validation_split=validation_split
        )
        
        test_datagen = ImageDataGenerator(
            rescale=1./255,
            validation_split=test_split
        )
        
        # 載入訓練資料
        train_generator = train_datagen.flow_from_directory(
            self.data_dir,
            target_size=self.image_size,
            batch_size=32,
            class_mode='categorical',
            subset='training',
            shuffle=True
        )
        
        # 載入驗證資料
        validation_generator = train_datagen.flow_from_directory(
            self.data_dir,
            target_size=self.image_size,
            batch_size=32,
            class_mode='categorical',
            subset='validation',
            shuffle=True
        )
        
        logger.info(f"訓練樣本數: {train_generator.samples}")
        logger.info(f"驗證樣本數: {validation_generator.samples}")
        logger.info(f"類別: {train_generator.class_indices}")
        
        return train_generator, validation_generator
    
    def create_model(self, use_pretrained=True):
        """創建模型"""
        logger.info("創建模型...")
        
        if use_pretrained:
            # 使用預訓練的 MobileNetV2
            base_model = keras.applications.MobileNetV2(
                input_shape=(*self.image_size, 3),
                include_top=False,
                weights='imagenet'
            )
            
            # 凍結基礎模型
            base_model.trainable = False
            
            # 添加分類層
            model = keras.Sequential([
                base_model,
                layers.GlobalAveragePooling2D(),
                layers.Dropout(0.2),
                layers.Dense(128, activation='relu'),
                layers.Dropout(0.2),
                layers.Dense(64, activation='relu'),
                layers.Dropout(0.2),
                layers.Dense(self.num_classes, activation='softmax')
            ])
        else:
            # 創建簡單的 CNN 模型
            model = keras.Sequential([
                layers.Conv2D(32, (3, 3), activation='relu', input_shape=(*self.image_size, 3)),
                layers.MaxPooling2D(2, 2),
                layers.Conv2D(64, (3, 3), activation='relu'),
                layers.MaxPooling2D(2, 2),
                layers.Conv2D(64, (3, 3), activation='relu'),
                layers.MaxPooling2D(2, 2),
                layers.Conv2D(128, (3, 3), activation='relu'),
                layers.MaxPooling2D(2, 2),
                layers.Flatten(),
                layers.Dense(512, activation='relu'),
                layers.Dropout(0.5),
                layers.Dense(256, activation='relu'),
                layers.Dropout(0.5),
                layers.Dense(self.num_classes, activation='softmax')
            ])
        
        # 編譯模型
        model.compile(
            optimizer=optimizers.Adam(learning_rate=0.001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        self.model = model
        logger.info(f"模型創建完成，參數數量: {model.count_params():,}")
        
        return model
    
    def train_model(self, train_generator, validation_generator, epochs=50):
        """訓練模型"""
        logger.info("開始訓練模型...")
        
        # 設定回調函數
        callbacks_list = [
            callbacks.EarlyStopping(
                monitor='val_loss',
                patience=5,
                restore_best_weights=True,
                verbose=1
            ),
            callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=3,
                min_lr=1e-7,
                verbose=1
            ),
            callbacks.ModelCheckpoint(
                filepath=os.path.join(self.model_dir, 'best_model.h5'),
                monitor='val_accuracy',
                save_best_only=True,
                verbose=1
            ),
            callbacks.CSVLogger(
                filename=os.path.join(self.model_dir, 'training_log.csv'),
                append=True
            )
        ]
        
        # 訓練模型
        self.history = self.model.fit(
            train_generator,
            epochs=epochs,
            validation_data=validation_generator,
            callbacks=callbacks_list,
            verbose=1
        )
        
        logger.info("模型訓練完成")
        return self.history
    
    def fine_tune_model(self, train_generator, validation_generator, epochs=20):
        """微調模型"""
        logger.info("開始微調模型...")
        
        # 解凍基礎模型的最後幾層
        base_model = self.model.layers[0]
        base_model.trainable = True
        
        # 只訓練最後幾層
        fine_tune_at = len(base_model.layers) - 20
        
        for layer in base_model.layers[:fine_tune_at]:
            layer.trainable = False
        
        # 重新編譯模型
        self.model.compile(
            optimizer=optimizers.Adam(learning_rate=0.0001),
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        # 微調訓練
        fine_tune_history = self.model.fit(
            train_generator,
            epochs=epochs,
            validation_data=validation_generator,
            verbose=1
        )
        
        logger.info("模型微調完成")
        return fine_tune_history
    
    def evaluate_model(self, test_generator):
        """評估模型"""
        logger.info("評估模型...")
        
        # 評估模型
        test_loss, test_accuracy = self.model.evaluate(test_generator, verbose=0)
        
        # 預測
        predictions = self.model.predict(test_generator)
        predicted_classes = np.argmax(predictions, axis=1)
        true_classes = test_generator.classes
        
        # 生成分類報告
        class_names = list(test_generator.class_indices.keys())
        report = classification_report(
            true_classes, 
            predicted_classes, 
            target_names=class_names,
            output_dict=True
        )
        
        # 生成混淆矩陣
        cm = confusion_matrix(true_classes, predicted_classes)
        
        logger.info(f"測試準確率: {test_accuracy:.4f}")
        logger.info(f"測試損失: {test_loss:.4f}")
        
        return {
            'test_accuracy': test_accuracy,
            'test_loss': test_loss,
            'classification_report': report,
            'confusion_matrix': cm,
            'predictions': predictions
        }
    
    def plot_training_history(self):
        """繪製訓練歷史"""
        if self.history is None:
            logger.warning("沒有訓練歷史可繪製")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        
        # 繪製準確率
        ax1.plot(self.history.history['accuracy'], label='訓練準確率')
        ax1.plot(self.history.history['val_accuracy'], label='驗證準確率')
        ax1.set_title('模型準確率')
        ax1.set_xlabel('Epoch')
        ax1.set_ylabel('準確率')
        ax1.legend()
        ax1.grid(True)
        
        # 繪製損失
        ax2.plot(self.history.history['loss'], label='訓練損失')
        ax2.plot(self.history.history['val_loss'], label='驗證損失')
        ax2.set_title('模型損失')
        ax2.set_xlabel('Epoch')
        ax2.set_ylabel('損失')
        ax2.legend()
        ax2.grid(True)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.model_dir, 'training_history.png'))
        plt.show()
    
    def plot_confusion_matrix(self, cm, class_names):
        """繪製混淆矩陣"""
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                    xticklabels=class_names, yticklabels=class_names)
        plt.title('混淆矩陣')
        plt.xlabel('預測類別')
        plt.ylabel('真實類別')
        plt.tight_layout()
        plt.savefig(os.path.join(self.model_dir, 'confusion_matrix.png'))
        plt.show()
    
    def save_model(self, model_path=None):
        """儲存模型"""
        if model_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            model_path = os.path.join(self.model_dir, f'waste_classifier_{timestamp}.h5')
        
        self.model.save(model_path)
        logger.info(f"模型已儲存至: {model_path}")
        
        # 儲存模型資訊
        model_info = {
            'model_path': model_path,
            'class_names': self.class_names,
            'num_classes': self.num_classes,
            'image_size': self.image_size,
            'created_at': datetime.now().isoformat(),
            'version': Config.APP_VERSION if hasattr(Config, 'APP_VERSION') else '1.0.0'
        }
        
        info_path = model_path.replace('.h5', '_info.json')
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(model_info, f, ensure_ascii=False, indent=2)
        
        return model_path
    
    def convert_to_tflite(self, model_path=None):
        """轉換為 TensorFlow Lite 格式"""
        if model_path is None:
            model_path = os.path.join(self.model_dir, 'best_model.h5')
        
        # 載入模型
        model = keras.models.load_model(model_path)
        
        # 轉換為 TFLite
        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        
        tflite_model = converter.convert()
        
        # 儲存 TFLite 模型
        tflite_path = model_path.replace('.h5', '.tflite')
        with open(tflite_path, 'wb') as f:
            f.write(tflite_model)
        
        logger.info(f"TFLite 模型已儲存至: {tflite_path}")
        return tflite_path
    
    def create_sample_data_structure(self):
        """創建範例資料結構"""
        logger.info("創建範例資料結構...")
        
        for category in self.class_names:
            category_dir = os.path.join(self.data_dir, category)
            os.makedirs(category_dir, exist_ok=True)
            
            # 創建 README 檔案
            readme_path = os.path.join(category_dir, 'README.md')
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"# {category} 類別圖片\n\n")
                f.write(f"請將 {category} 類別的垃圾圖片放在此目錄中。\n\n")
                f.write("建議：\n")
                f.write("- 每種類別至少需要 100 張圖片\n")
                f.write("- 圖片格式：JPG, PNG\n")
                f.write("- 圖片大小：建議 224x224 像素以上\n")
                f.write("- 圖片品質：清晰、光線充足\n")
                f.write("- 多角度拍攝：正面、側面、不同角度\n")
        
        logger.info("範例資料結構創建完成")
        logger.info(f"請將訓練圖片放入 {self.data_dir} 目錄中對應的類別資料夾")

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI 垃圾分類模型訓練')
    parser.add_argument('--data_dir', default='data/training', help='訓練資料目錄')
    parser.add_argument('--model_dir', default='models', help='模型儲存目錄')
    parser.add_argument('--epochs', type=int, default=50, help='訓練輪數')
    parser.add_argument('--fine_tune_epochs', type=int, default=20, help='微調輪數')
    parser.add_argument('--use_pretrained', action='store_true', help='使用預訓練模型')
    parser.add_argument('--create_structure', action='store_true', help='創建資料結構')
    parser.add_argument('--convert_tflite', action='store_true', help='轉換為 TFLite')
    
    args = parser.parse_args()
    
    # 創建訓練器
    trainer = WasteClassificationTrainer(args.data_dir, args.model_dir)
    
    if args.create_structure:
        trainer.create_sample_data_structure()
        return
    
    # 檢查資料目錄
    if not os.path.exists(args.data_dir):
        logger.error(f"資料目錄不存在: {args.data_dir}")
        logger.info("請先執行 --create_structure 創建資料結構")
        return
    
    try:
        # 準備資料
        train_gen, val_gen = trainer.prepare_data()
        
        # 創建模型
        trainer.create_model(args.use_pretrained)
        
        # 訓練模型
        trainer.train_model(train_gen, val_gen, args.epochs)
        
        # 微調模型
        if args.use_pretrained:
            trainer.fine_tune_model(train_gen, val_gen, args.fine_tune_epochs)
        
        # 評估模型
        results = trainer.evaluate_model(val_gen)
        
        # 繪製結果
        trainer.plot_training_history()
        trainer.plot_confusion_matrix(results['confusion_matrix'], list(train_gen.class_indices.keys()))
        
        # 儲存模型
        model_path = trainer.save_model()
        
        # 轉換為 TFLite
        if args.convert_tflite:
            trainer.convert_to_tflite(model_path)
        
        logger.info("訓練完成！")
        
    except Exception as e:
        logger.error(f"訓練過程中發生錯誤: {str(e)}")
        raise

if __name__ == '__main__':
    main()
