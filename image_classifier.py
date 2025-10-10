import os
import numpy as np
import cv2
from PIL import Image
import tensorflow as tf
from tensorflow import keras
import logging
from config import Config

logger = logging.getLogger(__name__)

class ImageClassifier:
    def __init__(self):
        self.model = None
        self.class_names = list(Config.WASTE_CATEGORIES.keys())
        self.load_model()
    
    def load_model(self):
        """載入預訓練模型"""
        try:
            if os.path.exists(Config.MODEL_PATH):
                # 載入自定義模型
                self.model = keras.models.load_model(Config.MODEL_PATH)
                logger.info("Custom model loaded successfully")
            else:
                # 使用預訓練的 MobileNet 模型
                self.model = self._create_pretrained_model()
                logger.info("Pretrained model created")
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            # 使用簡單的預訓練模型作為備用
            self.model = self._create_simple_model()
    
    def _create_pretrained_model(self):
        """創建基於 MobileNet 的預訓練模型"""
        # 載入預訓練的 MobileNet
        base_model = keras.applications.MobileNetV2(
            input_shape=(*Config.IMAGE_SIZE, 3),
            include_top=False,
            weights='imagenet'
        )
        
        # 凍結基礎模型
        base_model.trainable = False
        
        # 添加分類層
        model = keras.Sequential([
            base_model,
            keras.layers.GlobalAveragePooling2D(),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(128, activation='relu'),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(len(self.class_names), activation='softmax')
        ])
        
        # 編譯模型
        model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def _create_simple_model(self):
        """創建簡單的模型作為備用"""
        model = keras.Sequential([
            keras.layers.Conv2D(32, (3, 3), activation='relu', input_shape=(*Config.IMAGE_SIZE, 3)),
            keras.layers.MaxPooling2D(2, 2),
            keras.layers.Conv2D(64, (3, 3), activation='relu'),
            keras.layers.MaxPooling2D(2, 2),
            keras.layers.Conv2D(64, (3, 3), activation='relu'),
            keras.layers.Flatten(),
            keras.layers.Dense(64, activation='relu'),
            keras.layers.Dense(len(self.class_names), activation='softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def preprocess_image(self, image_path):
        """預處理圖片"""
        try:
            # 讀取圖片
            image = Image.open(image_path)
            
            # 轉換為 RGB（處理 RGBA 或其他格式）
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 調整大小
            image = image.resize(Config.IMAGE_SIZE)
            
            # 轉換為 numpy 陣列
            image_array = np.array(image)
            
            # 正規化
            image_array = image_array.astype('float32') / 255.0
            
            # 添加批次維度
            image_array = np.expand_dims(image_array, axis=0)
            
            return image_array
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {str(e)}")
            return None
    
    def classify_image(self, image_path):
        """對圖片進行垃圾分類"""
        try:
            # 預處理圖片
            processed_image = self.preprocess_image(image_path)
            
            if processed_image is None:
                return None
            
            # 進行預測
            predictions = self.model.predict(processed_image)
            
            # 取得最高機率的類別
            predicted_class_idx = np.argmax(predictions[0])
            confidence = float(predictions[0][predicted_class_idx])
            predicted_class = self.class_names[predicted_class_idx]
            
            # 如果信心度太低，返回 None
            if confidence < 0.3:
                logger.warning(f"Low confidence prediction: {confidence}")
                return None
            
            result = {
                'category': predicted_class,
                'confidence': confidence,
                'all_predictions': {
                    class_name: float(predictions[0][i]) 
                    for i, class_name in enumerate(self.class_names)
                }
            }
            
            logger.info(f"Classification result: {predicted_class} (confidence: {confidence:.3f})")
            return result
            
        except Exception as e:
            logger.error(f"Error classifying image: {str(e)}")
            return None
    
    def get_class_probabilities(self, image_path):
        """取得所有類別的機率分佈"""
        try:
            processed_image = self.preprocess_image(image_path)
            
            if processed_image is None:
                return None
            
            predictions = self.model.predict(processed_image)
            
            probabilities = {
                class_name: float(predictions[0][i]) 
                for i, class_name in enumerate(self.class_names)
            }
            
            # 按機率排序
            sorted_probabilities = sorted(
                probabilities.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            return sorted_probabilities
            
        except Exception as e:
            logger.error(f"Error getting class probabilities: {str(e)}")
            return None
    
    def save_model(self, model_path=None):
        """儲存模型"""
        try:
            if model_path is None:
                model_path = Config.MODEL_PATH
            
            # 確保目錄存在
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            
            self.model.save(model_path)
            logger.info(f"Model saved to {model_path}")
            
        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
    
    def train_model(self, training_data, validation_data, epochs=10):
        """訓練模型（需要實際的訓練資料）"""
        try:
            if self.model is None:
                self.model = self._create_pretrained_model()
            
            # 設定回調函數
            callbacks = [
                keras.callbacks.EarlyStopping(
                    monitor='val_loss',
                    patience=3,
                    restore_best_weights=True
                ),
                keras.callbacks.ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.5,
                    patience=2,
                    min_lr=1e-7
                )
            ]
            
            # 訓練模型
            history = self.model.fit(
                training_data,
                validation_data=validation_data,
                epochs=epochs,
                callbacks=callbacks,
                verbose=1
            )
            
            # 儲存模型
            self.save_model()
            
            logger.info("Model training completed")
            return history
            
        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            return None
    
    def evaluate_model(self, test_data):
        """評估模型效能"""
        try:
            if self.model is None:
                logger.error("No model loaded for evaluation")
                return None
            
            # 評估模型
            loss, accuracy = self.model.evaluate(test_data, verbose=0)
            
            logger.info(f"Model evaluation - Loss: {loss:.4f}, Accuracy: {accuracy:.4f}")
            
            return {
                'loss': loss,
                'accuracy': accuracy
            }
            
        except Exception as e:
            logger.error(f"Error evaluating model: {str(e)}")
            return None
