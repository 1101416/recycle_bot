import os
import logging
from PIL import Image
from config import Config
import google.generativeai as genai
from typing import Optional

logger = logging.getLogger(__name__)

# --- AI 模型設定 ---
# 從設定檔讀取支援的垃圾類別
WASTE_CATEGORIES_TEXT = ", ".join(Config.WASTE_CATEGORIES.keys())

# 給 AI 的指令 (Prompt)
SYSTEM_PROMPT = f"""
You are an expert in waste classification.
Your task is to identify the main object in the user's image and classify it into one of the following categories: {WASTE_CATEGORIES_TEXT}.
You must respond with only the single category name in lowercase English. For example: 'plastic'.
If the image is unclear or doesn't contain a classifiable item, respond with 'other'.
"""

class ImageClassifier:
    def __init__(self):
        """初始化 Gemini API"""
        self.model = None
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                logger.error("GOOGLE_API_KEY is not set. AI features will be disabled.")
                return
            
            genai.configure(api_key=api_key)
            # V V V 最終修正處 V V V
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            # ^ ^ ^ 最終修正處 ^ ^ ^
            logger.info("Gemini API configured successfully with 'gemini-1.5-flash-latest' model.")
        except Exception as e:
            logger.error(f"Error initializing Gemini API: {e}")

    def classify_image(self, image_path: str) -> Optional[dict]:
        """使用 Gemini API 進行垃圾分類"""
        if not self.model:
            logger.warning("Gemini model not loaded, classification skipped.")
            return None

        logger.info(f"Classifying image: {image_path}")
        try:
            # 讀取圖片
            img = Image.open(image_path)
            
            # 呼叫 Gemini Vision API
            response = self.model.generate_content([SYSTEM_PROMPT, img])
            
            # 清理並驗證 AI 的回應
            category = response.text.strip().lower()

            if category in Config.WASTE_CATEGORIES:
                logger.info(f"Gemini API classification result: '{category}'")
                # API 沒有傳統的信心度，我們給一個固定值表示成功
                return {
                    'category': category,
                    'confidence': 0.9  
                }
            else:
                logger.warning(f"Gemini API returned an invalid category: '{category}'. Defaulting to 'other'.")
                return {
                    'category': 'other',
                    'confidence': 0.5
                }

        except Exception as e:
            logger.error(f"Error during Gemini API call: {e}")
            return None

