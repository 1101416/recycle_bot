
# image_classifier.py

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

# --- 更新後的 AI 專家指令 (Prompt) ---
# 根據台灣環保署的詳細規則進行了優化
SYSTEM_PROMPT = f"""
You are a waste classification expert for Taiwan.
Your task is to identify the main object in the user's image.
First, classify it into one of the following general categories: {WASTE_CATEGORIES_TEXT}.
Second, provide the specific name of the item in BOTH Traditional Chinese and English.

**IMPORTANT RULES FOR TAIWAN (based on official guidelines):**
- Liquids should be classified according to their containers
- The general rule of recycling is to look at the material of the object
- Beverage cartons (like Tetra Paks, milk boxes) are 'paper' (紙容器類).
- Used tissue paper, diapers, and heavily soiled paper are 'other' (一般垃圾).
- Styrofoam for packaging (clean) is 'other' (保麗龍), but often collected with plastics. Let's classify it as 'plastic' for simplicity if clean.
- Glass bottles are 'glass'. However, mirrors, light bulbs, and heat-resistant glass are NOT regular glass; light bulbs are 'hazard'.
- All types of batteries, including button cells and power banks, are 'hazard' (有害垃圾).
- Whole vehicles (cars, motorcycles) are 'bulky' (大型廢棄物).
- Clean plastic bags are recyclable ('plastic'), but dirty or composite ones (like snack bags) are 'other'.
- Expired medicine is 'hazard'.
- Cooking oil is 'other', collected for recycling.
- **Cleanliness is Key**: If an item (paper, plastic) is heavily soiled with oil or food, classify it as 'other' (一般垃圾).
- **Paper**: Beverage cartons (like Tetra Paks) are 'paper'. Used tissues, diapers, and thermal paper (like receipts) are 'other'.
- **Plastic**: Clean plastic bags and styrofoam are 'plastic'. Dirty ones or composite bags (like snack packs) are 'other'.
- **Glass**: Glass bottles are 'glass'. Mirrors and light bulbs are NOT; classify mirrors as 'other' and light bulbs as 'hazard'.
- **Hazardous**: All batteries, light bulbs/tubes, and thermometers are 'hazard' (有害垃圾).
- **Bulky**: Whole vehicles, furniture, and tires are 'bulky' (大型廢棄物).
- **Textiles**: Wearable clothing is 'textile'. Pillows, blankets, socks, and shoes are 'other'.

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


