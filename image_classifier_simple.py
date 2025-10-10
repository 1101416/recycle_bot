import os
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
        """預處理圖片（簡化版）"""
        try:
            # 簡化版：只檢查檔案是否存在
            if os.path.exists(image_path):
                return True
            return False
        except Exception as e:
            logger.error(f"Error preprocessing image: {str(e)}")
            return False
    
    def classify_image(self, image_path):
        """對圖片進行垃圾分類（簡化版）"""
        try:
            # 簡化版：直接使用規則分類
            return self._fallback_classification(image_path)
                
        except Exception as e:
            logger.error(f"Error classifying image: {str(e)}")
            return self._fallback_classification(image_path)
    
    def _fallback_classification(self, image_path):
        """備用分類方法（簡化版）"""
        try:
            # 簡化版：基於檔案名稱的簡單分類
            filename = os.path.basename(image_path).lower()
            
            if 'plastic' in filename or 'bottle' in filename:
                category = 'plastic'
                confidence = 0.7
            elif 'paper' in filename or 'cardboard' in filename:
                category = 'paper'
                confidence = 0.7
            elif 'metal' in filename or 'can' in filename:
                category = 'metal'
                confidence = 0.7
            elif 'glass' in filename:
                category = 'glass'
                confidence = 0.7
            elif 'food' in filename or 'organic' in filename:
                category = 'organic'
                confidence = 0.7
            elif 'battery' in filename:
                category = 'battery'
                confidence = 0.7
            elif 'phone' in filename or 'computer' in filename:
                category = 'electronics'
                confidence = 0.7
            else:
                # 預設分類
                category = 'other'
                confidence = 0.5
            
            result = {
                'category': category,
                'confidence': confidence,
                'method': 'filename_based'
            }
            
            logger.info(f"Filename-based classification result: {category} (confidence: {confidence:.3f})")
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
