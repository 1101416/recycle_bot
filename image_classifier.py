import os
import logging
import re
from PIL import Image
from config import Config
import google.generativeai as genai
from typing import Optional

logger = logging.getLogger(__name__)

# --- AI 模型設定 ---
WASTE_CATEGORIES_TEXT = ", ".join(Config.WASTE_CATEGORIES.keys())

# 給 AI 的新版專家指令 (Prompt)，要求同時回傳中英文品項
SYSTEM_PROMPT = f"""
You are a waste classification expert for Taiwan.
Your task is to identify the main object in the user's image.
First, classify it into one of the following general categories: {WASTE_CATEGORIES_TEXT}.
Second, provide the specific name of the item in BOTH Traditional Chinese and English.

**IMPORTANT RULES FOR TAIWAN:**
- Beverage cartons (like Tetra Paks) are classified as 'paper'.
- Used tissue paper is not recyclable and must be classified as 'other'.

You MUST respond in the following format, and nothing else:
category: [lowercase_english_category], item_zh: [traditional_chinese_name], item_en: [english_name]
"""

class ImageClassifier:
    def __init__(self):
        self.model = None
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                logger.error("GOOGLE_API_KEY is not set. AI features will be disabled.")
                return
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
            logger.info("Gemini API configured successfully with 'gemini-2.5-flash-lite' model.")
        except Exception as e:
            logger.error(f"Error initializing Gemini API: {e}")

    def classify_image(self, image_path: str) -> Optional[dict]:
        if not self.model:
            logger.warning("Gemini model not loaded, classification skipped.")
            return None

        logger.info(f"Classifying image: {image_path}")
        try:
            img = Image.open(image_path)
            response = self.model.generate_content([SYSTEM_PROMPT, img])
            
            # 更新正規表達式以解析新的回應格式
            match = re.search(r"category:\s*(\w+),\s*item_zh:\s*([^,]+),\s*item_en:\s*(.+)", response.text.strip())
            
            if match:
                category = match.group(1).lower()
                item_name_zh = match.group(2).strip()
                item_name_en = match.group(3).strip()
                
                if category in Config.WASTE_CATEGORIES:
                    logger.info(f"Gemini API result: category='{category}', item_zh='{item_name_zh}', item_en='{item_name_en}'")
                    return {
                        'category': category,
                        'item_name_zh': item_name_zh,
                        'item_name_en': item_name_en,
                        'confidence': 0.95
                    }

            logger.warning(f"Gemini API returned an unparsable response: '{response.text}'. Defaulting to 'other'.")
            return {
                'category': 'other',
                'item_name_zh': '未知物品',
                'item_name_en': 'Unknown Item',
                'confidence': 0.5
            }

        except Exception as e:
            logger.error(f"Error during Gemini API call: {e}")
            return None
