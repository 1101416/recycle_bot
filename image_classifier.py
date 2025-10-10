import os
import numpy as np
from PIL import Image
import logging
from config import Config

# 嘗試匯入 TFLite，如果失敗則提示使用者
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    tflite = None

logger = logging.getLogger(__name__)

class ImageClassifier:
    def __init__(self):
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.class_names = list(Config.WASTE_CATEGORIES.keys())
        self.load_model()

    def load_model(self):
        """載入 TFLite 模型"""
        if tflite is None:
            logger.error("tflite_runtime is not installed. Please install it to use AI features.")
            return

        # 模型路徑從 .h5 改為 .tflite
        tflite_model_path = Config.MODEL_PATH.replace('.h5', '.tflite')
        
        try:
            if os.path.exists(tflite_model_path):
                self.interpreter = tflite.Interpreter(model_path=tflite_model_path)
                self.interpreter.allocate_tensors()
                self.input_details = self.interpreter.get_input_details()
                self.output_details = self.interpreter.get_output_details()
                logger.info(f"TFLite model loaded successfully from {tflite_model_path}")
            else:
                logger.error(f"TFLite model not found at {tflite_model_path}. Please generate and add it to the 'models' directory.")
        except Exception as e:
            logger.error(f"Error loading TFLite model: {str(e)}")

    def preprocess_image(self, image_path):
        """預處理圖片以符合 TFLite 模型輸入"""
        try:
            image = Image.open(image_path).convert('RGB')
            # 從 input_details 獲取模型需要的圖片尺寸
            _, height, width, _ = self.input_details[0]['shape']
            image = image.resize((width, height))
            
            image_array = np.array(image, dtype=np.float32)
            image_array = np.expand_dims(image_array, axis=0)
            
            # 根據模型的輸入類型進行正規化
            if self.input_details[0]['dtype'] == np.uint8:
                return image_array # 如果模型是量化的，不需要正規化
            else:
                return (image_array / 127.5) - 1.0 # 常見的正規化方式
            
        except Exception as e:
            logger.error(f"Error preprocessing image for TFLite: {str(e)}")
            return None

    def classify_image(self, image_path):
        """使用 TFLite 模型進行垃圾分類"""
        if self.interpreter is None:
            logger.warning("TFLite interpreter not loaded, classification skipped.")
            return None
        
        try:
            processed_image = self.preprocess_image(image_path)
            if processed_image is None:
                return None

            # 設定模型的輸入
            self.interpreter.set_tensor(self.input_details[0]['index'], processed_image)
            # 執行預測
            self.interpreter.invoke()
            # 取得預測結果
            predictions = self.interpreter.get_tensor(self.output_details[0]['index'])[0]

            predicted_class_idx = np.argmax(predictions)
            # TFLite 的輸出通常是 0-255 的整數或 0-1 的浮點數，需要轉換
            confidence = float(predictions[predicted_class_idx] / 255.0) if np.issubdtype(predictions.dtype, np.integer) else float(predictions[predicted_class_idx])
            
            predicted_class = self.class_names[predicted_class_idx]

            if confidence < 0.3:
                logger.warning(f"Low confidence TFLite prediction: {confidence}")
                return None

            result = {
                'category': predicted_class,
                'confidence': confidence
            }
            logger.info(f"TFLite Classification result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error classifying image with TFLite: {str(e)}")
            return None
