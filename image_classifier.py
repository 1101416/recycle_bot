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

* **Rule 0: Special Items First**
    * Dead Animals (cat, dog, bird): MUST classify as 'animal'.
    * Currency (banknotes, coins): MUST classify as 'money'.
    * Hazardous Items (Batteries, light bulbs/tubes, mercury thermometers, expired medicine, gas canisters): MUST classify as 'hazard'.

* **Rule 1: Paper vs. Content**
    * If the image shows paper with text/images (flyer, magazine, newspaper, packaging box), identify the **paper object itself** (e.g., '傳單', '雜誌', '紙箱') and classify based on its material ('paper' or 'other' if soiled/composite), **NOT** the content depicted (like a product on the flyer). Beverage cartons (Tetra Pak) count as 'paper'.

* **Rule 2: Material-First (Plastics Focus)**
    * Determine the item's primary material. Focus on the main container/body if components differ (e.g., a plastic spray bottle is 'plastic', ignore the nozzle).
    * **Plastic Identification**: Look for recycling symbols if visible.
        * **Highly Recyclable (Prioritize 'plastic')**: #1 (PET - bottles, trays), #2 (HDPE - milk jugs, some bags), #5 (PP - yogurt cups, microwave containers, alcohol bottles). Classify these as 'plastic' if clean.
        * **Less Recyclable (Check Cleanliness/Composite)**: #4 (LDPE - plastic bags, cling film), #6 (PS - styrofoam, Yakult bottles). If clean and not composite, classify as 'plastic'. If dirty, oily, or mixed material (like bubble wrap), classify as 'other'. Styrofoam: needs "Clean, Tear off tape, Bagged" (清、撕、裝).
        * **Difficult/Non-Recyclable (Prioritize 'other')**: #3 (PVC - pipes, raincoats, sometimes cling film), #7 (OTHER - includes PLA, complex composites like some water bottles, eyeglass frames). Classify these as 'other'.
    * **Metal Identification**: Cans (iron/aluminum), clean metal tools → 'metal'.
    * **Glass Identification**: Glass bottles/jars → 'glass'. (Mirrors → 'other').

* **Rule 3: Cleanliness is Key**
    * If any potentially recyclable item (especially paper, plastic #1, #2, #4, #5, #6) is heavily soiled, oily, or food-contaminated → 'other'.

* **Rule 4: Specific Item Rules & Exceptions**
    * **ewaste**: ALL electronics & appliances (TVs, phones, laptops, chargers, keyboards, power banks), **even if broken**, are 'ewaste'.
    * **textile**: Clean, wearable clothing → 'textile'. (Pillows, blankets, socks, shoes, bags, stuffed animals → 'other').
    * **bulky**: Large furniture (mattresses, sofas), vehicles, tires → 'bulky'.
    * **food**: Cooked or raw food scraps → 'food'.
    * **Common Non-Recyclable Plastics (Always 'other')**: Dirty/oily plastic bags, opaque/colored shopping bags (破壞袋), bubble wrap, refill packs (補充包), cling film (保鮮膜), plastic floss picks (牙線棒), flip-flops (夾腳拖), yoga mats (瑜珈墊), toothbrushes (牙刷), complex phone cases (複合材質手機殼).

---
**5. Naming & Uncertainty Rules**
* **Naming**: Give concise names (1-4 words). If the object is paper with content (flyer, box), name the paper object (e.g., '廣告傳單', '紙盒'), not the content. Use label text if it helps identify the *object type* (e.g., 'PET 咖啡瓶').
* **Uncertainty**: If truly uncertain after applying all rules, choose 'other' and set item_zh to '疑似: <簡短描述>' and item_en to 'suspected: <short description>'. Avoid using this if a rule clearly applies (e.g., a dirty plastic bottle is 'other', not 'suspected').

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








