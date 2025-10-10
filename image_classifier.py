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

# 給 AI 的新版專家指令 (Prompt)，加入了 PDF 中的台灣在地規則
SYSTEM_PROMPT = f"""
You are an expert in waste classification for Taiwan, referencing official government documents.
Your task is to identify the main object in the user's image.
First, classify it into one of the following general categories: {WASTE_CATEGORIES_TEXT}.
Second, provide the specific name of the item in Traditional Chinese (e.g., '衛生紙', '鋁箔包', '寶特瓶').

**IMPORTANT RULES FOR TAIWAN (from a government PDF):**
- **Paper Containers ('紙容器')**: Beverage cartons (like Tetra Paks, milk cartons) must be cleaned and are classified as 'paper'. This is a special category.
- **Non-recyclable Paper**: Used tissue paper ('衛生紙'), paper diapers ('紙尿褲'), thermal paper ('感熱紙' like receipts), and dirty paper are NOT recyclable and must be classified as 'other'.
- **Recyclable Paper**: Clean paper, cardboard, and newspapers are 'paper'.
- **Plastics ('塑膠類')**: Clean plastic bottles (PET), containers (PP, PE), and plastic bags are 'plastic'.
- **Metals ('金屬類')**: Iron and aluminum cans are 'metal'.
- **Glass ('玻璃類')**: Glass bottles and containers are 'glass'.

Based on these rules, you MUST respond in the following format, and nothing else:
category: [lowercase_english_category], item: [traditional_chinese_item_name]
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
            
            # 使用正規表達式解析 AI 的回應
            match = re.search(r"category:\s*(\w+),\s*item:\s*(.+)", response.text.strip())
            
            if match:
                category = match.group(1).lower()
                item_name = match.group(2).strip()
                
                if category in Config.WASTE_CATEGORIES:
                    logger.info(f"Gemini API result: category='{category}', item='{item_name}'")
                    return {
                        'category': category,
                        'item_name': item_name,
                        'confidence': 0.95 # 提高信心度，因為我們給了更明確的指令
                    }

            logger.warning(f"Gemini API returned an unparsable response: '{response.text}'. Defaulting to 'other'.")
            return {
                'category': 'other',
                'item_name': '未知物品',
                'confidence': 0.5
            }

        except Exception as e:
            logger.error(f"Error during Gemini API call: {e}")
            return None
