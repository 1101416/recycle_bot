# image_classifier.py

import os
import logging
import re
from PIL import Image
from config import Config
import google.generativeai as genai
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# --- AI 模型設定 ---
WASTE_CATEGORIES_TEXT = ", ".join(Config.WASTE_CATEGORIES.keys())

# --- 提示詞 1：用於圖片辨識 (G -> R) ---
CLASSIFICATION_SYSTEM_PROMPT = f"""
You are a waste classification expert for Taiwan, following official guidelines.
Your task is to identify the main object in the user's image.
First, classify it into ONE of the following general categories: {WASTE_CATEGORIES_TEXT}.
Second, provide the specific name of the item in BOTH Traditional Chinese and English.

**IMPORTANT GUIDELINES FOR TAIWAN:**
- **Cleanliness is Key**: If an item (paper, plastic) is heavily soiled with oil or food, classify it as 'other' (一般垃圾).
- **Paper**: Beverage cartons (like Tetra Paks) are 'paper'. Used tissues, diapers, and thermal paper (like receipts) are 'other'.
- **Plastic**: Clean plastic bags and styrofoam are 'plastic'. Dirty ones or composite bags (like snack packs) are 'other'.
- **Perfume Bottles**: The container is the key. Classify them as 'glass' as they are most commonly glass bottles.
- **Glass**: Glass bottles are 'glass'. Mirrors and light bulbs are NOT; classify mirrors as 'other' and light bulbs as 'hazard'.
- **Hazardous**: All batteries, light bulbs/tubes, and thermometers are 'hazard' (有害垃圾).
- **Bulky**: Whole vehicles, furniture, and tires are 'bulky' (大型廢棄物).
- **Textiles**: Wearable clothing is 'textile'. Pillows, blankets, socks, and shoes are 'other'.

You MUST respond in the following format, and nothing else:
category: [lowercase_english_category], item_zh: [traditional_chinese_name], item_en: [english_name]
"""

# --- 提示詞 2：用於 RAG 回答生成 (A -> G) ---
RAG_SYSTEM_PROMPT = """
You are a helpful and friendly waste classification assistant in Taiwan.
A user wants to know how to dispose of an item. I have provided you with the official guidelines in the [CONTEXT].
Your task is to generate a conversational, clear, and step-by-step response based *ONLY* on the provided context.
- You MUST answer in the language requested (e.g., zh-TW or en).
- Be friendly and start with a confirmation (e.g., "您詢問的是「香水」嗎？").
- Clearly explain the 'Disposal Method' and 'Tips' from the context.
- **Critical Rule**: Do NOT add, invent, or assume any information that is not in the [CONTEXT]. Stick strictly to the provided facts.
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
        """
        步驟 G -> R：辨識圖片並生成結構化關鍵字。
        """
        if not self.model:
            logger.warning("Gemini model not loaded, classification skipped.")
            return None

        logger.info(f"Classifying image: {image_path}")
        try:
            img = Image.open(image_path)
            # 使用提示詞 1
            response = self.model.generate_content([CLASSIFICATION_SYSTEM_PROMPT, img])
            
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

    def generate_rag_answer(self, waste_info: Dict, classification_result: Dict, user_lang: str) -> str:
        """
        步驟 A -> G：使用檢索到的上下文(waste_info)來生成最終的對話式回答。
        """
        if not self.model:
            logger.warning("Gemini model not loaded, RAG generation skipped.")
            return "AI model is not available."
        
        # 步驟 A (Augment): 建立增強提示詞
        
        # 確定要用中文還是英文名稱
        item_name = classification_result['item_name_zh'] if user_lang == 'zh-TW' else classification_result['item_name_en']
        
        # 格式化我們的上下文 (R)
        context = f"""
        [CONTEXT]
        - Language to use: {user_lang}
        - User's Item: {item_name}
        - Official Category: {waste_info['category_name']} ({waste_info['category_name_zh']})
        - Disposal Method: {waste_info['disposal_method']}
        - Tips: {waste_info['tips']}
        """

        logger.info(f"Generating RAG answer with context: {context}")
        
        try:
            # 步驟 G (Generate): 第二次呼叫 AI
            # 使用提示詞 2
            response = self.model.generate_content([RAG_SYSTEM_PROMPT, context])
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error during RAG answer generation: {e}")
            # RAG 生成失敗的後備方案
            if user_lang == 'zh-TW':
                return f"抱歉，AI 助理目前無法總結。這是有關「{item_name}」的原始資料：\n\n處理方式：\n{waste_info['disposal_method']}\n\n提醒：\n{waste_info['tips']}"
            else:
                return f"Sorry, the AI assistant cannot summarize right now. Here is the raw data for '{item_name}':\n\nMethod:\n{waste_info['disposal_method']}\n\nTips:\n{waste_info['tips']}"
