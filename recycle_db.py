
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config import Config

logger = logging.getLogger(__name__)

class RecycleDatabase:
    def __init__(self, db_path='database.db'):
        self.db_path = db_path
    
    def get_waste_info(self, category: str, language: str = 'zh-TW') -> Optional[Dict]:
        """
        (智慧通用查詢 v2.1 - 已修正 Bug 2)
        依據 category 和 language，查詢通用規則。
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                category_name_zh = Config.WASTE_CATEGORIES.get(category)
                if not category_name_zh: return None

                result = None
                
                if language == 'en':
                    cursor.execute(
                        "SELECT category, name, disposal_method, tips FROM waste_info WHERE category = ? AND language = 'en'", (category,)
                    )
                    all_cat_rules = cursor.fetchall()
                    
                    # --- vvv 修正 Bug 2 vvv ---
                    # 修正：使用 'in' 進行彈性比對 (例如 "ewaste" in "e-waste")
                    # 而不是 '==' ( "ewaste" == "e-waste" -> False)
                    for rule in all_cat_rules:
                        if category.lower() in rule[1].lower(): 
                            result = rule
                            break
                    # --- ^^^ 修正 Bug 2 ^^^ ---
                
                else: # 中文查詢
                     cursor.execute(
                        "SELECT category, name, disposal_method, tips FROM waste_info WHERE category = ? AND name = ? AND language = 'zh-TW' LIMIT 1",
                        (category, category_name_zh)
                    )
                     result = cursor.fetchone()


                if result:
                    return {
                        'category': result[0],
                        'category_name': result[1],
                        'category_name_zh': category_name_zh,
                        'disposal_method': result[2],
                        'tips': result[3]
                    }
                
                logger.warning(f"Could not find a generic rule for category '{category}' in language '{language}'.")
                return None
        except Exception as e:
            logger.error(f"Error getting general waste info for category '{category}': {e}")
            return None

    def get_specific_waste_info(self, category: str, item_name: str, language: str = 'zh-TW') -> Optional[Dict]:
        """
        (智慧查詢引擎 v3.1 - 已修正 Bug 1)
        使用多關鍵字匹配，並動態排除所有通用規則
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT category, name, disposal_method, tips FROM waste_info WHERE language = ?", (language,))
                all_rules = cursor.fetchall()
                
                generic_names_zh = list(Config.WASTE_CATEGORIES.values())
                # (英文的通用規則名稱在 database.py 中不統一，例如 "E-Waste", "Food Waste")
                # 我們假設英文通用規則的 name 欄位都包含 Waste 或 'Paper', 'Plastic', 'Metal', 'Glass', 'Textile'
                generic_names_en = [cat.capitalize() for cat in Config.WASTE_CATEGORIES.keys()] + ["Waste"]

                best_match = None
                item_to_check = item_name if language == 'zh-TW' else item_name.lower()
                
                for rule in all_rules:
                    db_keywords_str = rule[1]
                    
                    # 智慧排除：
                    # 1. 排除中文通用規則 (e.g., "紙類", "廚餘")
                    if db_keywords_str in generic_names_zh:
                        continue
                    
                    # 2. 排除英文通用規則 (e.g., "Paper", "E-Waste")
                    is_generic_en = False
                    if language == 'en':
                        for gen_name in generic_names_en:
                            if gen_name in db_keywords_str:
                                is_generic_en = True
                                break
                    if is_generic_en:
                        continue
                    
                    
                    db_keywords = [kw.strip().lower() if language == 'en' else kw.strip() for kw in db_keywords_str.split(',')]
                    
                    for keyword in db_keywords:
                        
                        # --- vvv 修正 Bug 1 vvv ---
                        # 修正：檢查 AI 辨識的物品 (item_to_check) 是否為 資料庫關鍵字 (keyword) 的一部分
                        # (例如： if "battery" in "used batteries")
                        if item_to_check in keyword:
                        # --- ^^^ 修正 Bug 1 ^^^ ---
                            best_match = rule
                            break
                    if best_match:
                        break

                if best_match:
                    logger.info(f"Expert rule found for '{item_name}', using rule for keywords '{best_match[1]}'.")
                    correct_category = best_match[0]
                    category_name_zh = Config.WASTE_CATEGORIES.get(correct_category)
                    category_name_display = best_match[1].split(',')[0]

                    return {
                        'category': correct_category,
                        'category_name': category_name_display,
                        'category_name_zh': category_name_zh,
                        'disposal_method': best_match[2],
                        'tips': best_match[3]
                    }
                
                logger.info(f"No expert rule found for '{item_name}', falling back to general category '{category}'.")
                # 如果找不到特定規則，回傳「通用規則」（現在 Bug 2 已修復，這裡會正常運作）
                return self.get_waste_info(category, language)
        except Exception as e:
            logger.error(f"Error getting specific waste info: {e}")
            return self.get_waste_info(category, language)

    # --- 以下為使用者資料相關函式，維持不變 ---
    
    def get_or_create_user(self, user_id: str, language: str = 'zh-TW') -> Dict:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                user = cursor.fetchone()
                if user:
                    cursor.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
                    conn.commit()
                    return {'user_id': user[0], 'language': user[1], 'created_at': user[2], 'last_active': user[3], 'eco_points': user[4]}
                else:
                    cursor.execute('INSERT INTO users (user_id, language, created_at, last_active, eco_points) VALUES (?, ?, ?, ?, ?)', (user_id, language, datetime.now(), datetime.now(), 0))
                    conn.commit()
                    return {'user_id': user_id, 'language': language, 'created_at': datetime.now().isoformat(), 'last_active': datetime.now().isoformat(), 'eco_points': 0}
        except Exception as e:
            logger.error(f"Error getting/creating user: {e}")
            return None
    
    def get_user_language(self, user_id: str) -> Optional[str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting user language: {e}")
            return None
    
    def update_user_language(self, user_id: str, language: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET language = ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?', (language, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user language: {e}")
            return False
    
    def record_classification(self, user_id: str, category: str, confidence: float, image_path: str = None, is_correct: bool = None, feedback: str = None) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO classifications (user_id, category, confidence, image_path, is_correct, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (user_id, category, confidence, image_path, is_correct, feedback, datetime.now()))
                if is_correct:
                    cursor.execute('UPDATE users SET eco_points = eco_points + 1 WHERE user_id = ?', (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error recording classification: {e}")
            return False
    
    def get_user_stats(self, user_id: str) -> Dict:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM classifications WHERE user_id = ?', (user_id,))
                total_classifications = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM classifications WHERE user_id = ? AND is_correct = 1', (user_id,))
                correct_classifications = cursor.fetchone()[0]
                accuracy_rate = (correct_classifications / total_classifications * 100) if total_classifications > 0 else 0
                cursor.execute("SELECT category, COUNT(*) as count FROM classifications WHERE user_id = ? GROUP BY category ORDER BY count DESC LIMIT 1", (user_id,))
                most_common = cursor.fetchone()
                most_common_category = most_common[0] if most_common else '無'
                cursor.execute('SELECT eco_points FROM users WHERE user_id = ?', (user_id,))
                eco_points_result = cursor.fetchone()
                eco_points = eco_points_result[0] if eco_points_result else 0
                return {'total_classifications': total_classifications, 'correct_classifications': correct_classifications, 'accuracy_rate': accuracy_rate, 'most_common_category': most_common_category, 'eco_points': eco_points}
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {'total_classifications': 0, 'correct_classifications': 0, 'accuracy_rate': 0, 'most_common_category': '無', 'eco_points': 0}
