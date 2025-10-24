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
Your task is to identify the main object in the user's input (which could be an image OR text).
First, classify it into one of the following general categories: {WASTE_CATEGORIES_TEXT}.
Second, provide the specific name of the item in BOTH Traditional Chinese and English.

---
**Core Instructions (Must Follow)**
1.  **Analyze Input**: Your input may be an image OR text. If it is text (e.g., "Fired chicken", "炸雞"), analyze the text as if it were an object.
2.  **Animal Rule**: If the input contains a dead animal (cat, dog, bird, etc.), you MUST classify it as 'animal'.
3.  **Material Principle**: The general rule of recycling is to look at the material of the object.
4.  **Cleanliness is Key**: If a recyclable item (paper, plastic) is heavily soiled with oil or food, classify it as 'other' (一般垃圾).

---
**Taiwan Recycling Guidelines by Category (All 11 Categories)**

* **food**: Cooked food (like "Fried chicken") and raw food scraps are 'food' (廚餘).
* **paper**: Beverage cartons (like Tetra Paks) are 'paper'. Used tissues, diapers, and thermal paper (like receipts) are 'other'.
* **plastic**: Clean plastic bags and clean styrofoam are 'plastic'. Dirty ones or composite bags (like snack packs) are 'other'.
* **metal**: Metal containers (iron/aluminum cans) and metal tools (keys, scissors) are 'metal'. (Note: Pressurized gas cylinders are 'hazard').
* **glass**: Glass bottles and containers are 'glass'. (Note: Mirrors are 'other', light bulbs are 'hazard').
* **textile**: Wearable clothing (shirts, pants, jackets) is 'textile'. (Note: Pillows, blankets, socks, and shoes are 'other').
* **ewaste**: Appliances (TVs, refrigerators, phones, rice cookers) and IT equipment (laptops, monitors, keyboards, chargers) are 'ewaste'.
* **hazard**: All batteries (button cells, power banks), light bulbs/tubes, thermometers, and expired medicine are 'hazard' (有害垃圾).
* **bulky**: Whole vehicles (cars, motorcycles), large furniture (mattresses, sofas), and tires are 'bulky' (大型廢棄物).
* **animal**: Dead animals (pets, strays, birds) are 'animal'.
* **other**: Items that cannot be recycled, such as cooking oil (collected separately), dirty recyclables, mirrors, or complex composite materials.

---
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

    def _parse_gemini_response(self, response_text: str) -> Optional[dict]:
        """
        (共用函式) 解析 Gemini 的回應
        """
        match = re.search(r"category:\s*(\w+),\s*item_zh:\s*([^,]+),\s*item_en:\s*(.+)", response_text.strip())
        
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
                    'confidence': 0.95  # AI-based, assume high confidence
                }
            else:
                 logger.warning(f"Gemini returned an invalid category: '{category}'. Full response: '{response_text}'")

        logger.warning(f"Gemini API returned an unparsable response: '{response_text}'. Defaulting to 'other'.")
        return {
            'category': 'other',
            'item_name_zh': '未知物品',
            'item_name_en': 'Unknown Item',
            'confidence': 0.5
        }

    def classify_image(self, image_path: str) -> Optional[dict]:
        if not self.model:
            logger.warning("Gemini model not loaded, image classification skipped.")
            return None

        logger.info(f"Classifying image: {image_path}")
        try:
            img = Image.open(image_path)
            response = self.model.generate_content([SYSTEM_PROMPT, img])
            return self._parse_gemini_response(response.text)

        except Exception as e:
            logger.error(f"Error during Gemini API call for image: {e}")
            return None

    # --- vvv 新增的函式 vvv ---
    def classify_text(self, text_input: str) -> Optional[dict]:
        if not self.model:
            logger.warning("Gemini model not loaded, text classification skipped.")
            return None

        logger.info(f"Classifying text: {text_input}")
        try:
            # 將使用者的文字和提示詞一起發送
            response = self.model.generate_content([SYSTEM_PROMPT, text_input])
            return self._parse_gemini_response(response.text)

        except Exception as e:
            logger.error(f"Error during Gemini API call for text: {e}")
            return None





