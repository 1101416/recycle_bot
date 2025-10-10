import os
import numpy as np
from PIL import Image
import logging
from config import Config

logger = logging.getLogger(__name__)

class ImageClassifier:
    def __init__(self):
        self.class_names = list(Config.WASTE_CATEGORIES.keys())
        self.model = None
        self.load_model()
    
    def load_model(self):
        """載入預訓練模型"""
        try:
            # 直接使用規則分類，不依賴 TensorFlow
            logger.info("Using rule-based classification")
            self.model = None
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            self.model = None
    
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
            if self.model is not None:
                # 使用 AI 模型分類
                processed_image = self.preprocess_image(image_path)
                
                if processed_image is None:
                    return self._fallback_classification(image_path)
                
                # 進行預測
                predictions = self.model.predict(processed_image)
                
                # 取得最高機率的類別
                predicted_class_idx = np.argmax(predictions[0])
                confidence = float(predictions[0][predicted_class_idx])
                predicted_class = self.class_names[predicted_class_idx]
                
                # 如果信心度太低，使用備用分類
                if confidence < 0.3:
                    logger.warning(f"Low confidence prediction: {confidence}")
                    return self._fallback_classification(image_path)
                
                result = {
                    'category': predicted_class,
                    'confidence': confidence,
                    'all_predictions': {
                        class_name: float(predictions[0][i]) 
                        for i, class_name in enumerate(self.class_names)
                    }
                }
                
                logger.info(f"AI Classification result: {predicted_class} (confidence: {confidence:.3f})")
                return result
            else:
                # 使用備用分類方法
                return self._fallback_classification(image_path)
                
        except Exception as e:
            logger.error(f"Error classifying image: {str(e)}")
            return self._fallback_classification(image_path)
    
    def _fallback_classification(self, image_path):
        """備用分類方法（基於圖片特徵的簡單規則）"""
        try:
            # 讀取圖片
            image = Image.open(image_path)
            
            # 轉換為 RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 取得圖片資訊
            width, height = image.size
            image_array = np.array(image)
            
            # 計算平均顏色
            avg_color = np.mean(image_array, axis=(0, 1))
            
            # 計算顏色分佈
            color_std = np.std(image_array, axis=(0, 1))
            
            # 簡單的規則分類
            if avg_color[0] > 200 and avg_color[1] > 200 and avg_color[2] > 200:
                # 白色/透明物體 - 可能是塑膠
                category = 'plastic'
                confidence = 0.6
            elif avg_color[0] < 100 and avg_color[1] < 100 and avg_color[2] < 100:
                # 深色物體 - 可能是電池或電子產品
                category = 'battery'
                confidence = 0.5
            elif avg_color[1] > avg_color[0] and avg_color[1] > avg_color[2]:
                # 綠色物體 - 可能是廚餘
                category = 'organic'
                confidence = 0.5
            elif np.mean(color_std) < 30:
                # 顏色變化小 - 可能是金屬
                category = 'metal'
                confidence = 0.5
            else:
                # 預設分類
                category = 'other'
                confidence = 0.4
            
            result = {
                'category': category,
                'confidence': confidence,
                'method': 'rule_based'
            }
            
            logger.info(f"Fallback classification result: {category} (confidence: {confidence:.3f})")
            return result
            
        except Exception as e:
            logger.error(f"Error in fallback classification: {str(e)}")
            return {
                'category': 'other',
                'confidence': 0.3,
                'method': 'default'
            }
    
    def get_class_probabilities(self, image_path):
        """取得所有類別的機率分佈"""
        try:
            result = self.classify_image(image_path)
            
            if result and 'all_predictions' in result:
                probabilities = result['all_predictions']
            else:
                # 如果沒有詳細預測，創建簡單的分佈
                probabilities = {class_name: 0.0 for class_name in self.class_names}
                probabilities[result['category']] = result['confidence']
            
            # 按機率排序
            sorted_probabilities = sorted(
                probabilities.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            return sorted_probabilities
            
        except Exception as e:
            logger.error(f"Error getting class probabilities: {str(e)}")
            return []
