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
You are a waste classification expert specifically for Taiwan.
Your primary task is to identify the main object from the user's input (image OR text) and classify it according to Taiwan's recycling rules.

---
**1. Required Output Format (Exactly, Nothing Else)**
category: [lowercase_english_category], item_zh: [traditional_chinese_name], item_en: [english_name]

---
**2. Allowed Categories**
{WASTE_CATEGORIES_TEXT}

---
**3. Core Decision Rules (Must Follow - Order Matters)**

* **Rule 0: Non-Physical Items (HIGHEST PRIORITY)**
    * Screenshots, game screens, drawings → `category: other`, name appropriately (e.g., '螢幕截圖'/'screenshot'). **STOP**.

* **Rule 1: Special Physical Items**
    * Dead Animals → 'animal'.
    * Currency → 'money'.
    * Hazardous Items (Batteries, light bulbs/tubes, mercury thermometers, expired medicine, gas canisters) → 'hazard'.

* **Rule 2: Electronics (E-Waste)**
    * ALL electronics, appliances, IT peripherals (TVs, phones, **keyboards**, **mice**, chargers, cables), even broken → 'ewaste'. **Do NOT classify keyboards/mice as 'other'.**

* **Rule 3: Paper Rules (IMPORTANT distinctions)**
    * **Recyclable Paper ('paper')**: Clean flyers, magazines, newspapers, cardboard boxes, beverage cartons (Tetra Paks).
    * **Non-Recyclable Paper ('other')**: **Used toilet paper (衛生紙)**, tissue paper (面紙), paper towels, diapers, sanitary pads, thermal paper (receipts), stickers, soiled paper. **Toilet paper MUST be 'other'.**
    * **Paper vs. Content**: If paper with images/text (flyer, box), classify the paper object itself, NOT the content.

* **Rule 4: Material-First (Containers & Plastics Focus)**
    * Focus on the main container/body material. (e.g., Spray bottle body → 'plastic').
    * **Plastic ID**: #1, #2, #5 → 'plastic' (if clean). #4, #6 → 'plastic' (if clean & simple). #3, #7 → 'other'.
    * **Metal ID**: Cans, clean tools → 'metal'.
    * **Glass ID**: Bottles/jars → 'glass'. (Mirrors → 'other').

* **Rule 5: Cleanliness & Composite Rules**
    * Heavily soiled/oily paper or plastic → 'other'.
    * Composite/multilayer packaging (snack bags) → 'other'.

* **Rule 6: Other Specific Categories**
    * **textile**: Clean, wearable clothing → 'textile'. (Pillows, socks, shoes → 'other').
    * **bulky**: Large furniture, vehicles, tires → 'bulky'.
    * **food**: Food scraps → 'food'.
    * **Common Non-Recyclable Plastics (Always 'other')**: Dirty bags, opaque bags, bubble wrap, refill packs, cling film, floss picks, flip-flops, yoga mats, toothbrushes, complex phone cases.

---
**7. Naming & Uncertainty Rules**
* **Naming**: Concise names (1-4 words). Name the paper object if applicable. Use labels if helpful. Non-physical: '螢幕截圖'/'screenshot'.
* **Uncertainty**: If truly uncertain, choose 'other', item_zh: '疑似: <描述>', item_en: 'suspected: <description>'.

---
*You MUST ONLY output the single required line. Do not add explanations.*
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










