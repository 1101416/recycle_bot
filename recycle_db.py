# 檔案: recycle_db.py
# (此版本已修正專家規則搜尋邏輯，優先匹配 category)

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
    
    def _format_rule_response(self, rule_tuple: Tuple, category_key: str) -> Optional[Dict]:
        """(輔助函式) 將資料庫回傳的 tuple 格式化為 dict"""
        if not rule_tuple:
            return None
        
        category_name_zh = Config.WASTE_CATEGORIES.get(category_key, '其他')
        
        # 修正：確保回傳的 category key 與 AI 的一致
        # rule_tuple[0] 可能是 'other' (來自玻璃規則), 但 category_key 是 'bulky' (來自AI)
        # 我們應該使用 AI 的 category_key 作為主要分類依據
        return {
            'category': category_key, 
            'category_name': rule_tuple[1],      
            'category_name_zh': category_name_zh, 
            'disposal_method': rule_tuple[2],
            'tips': rule_tuple[3]
        }

    def get_specific_waste_info(self, category: str, item_name: str, language: str = 'zh-TW') -> Optional[Dict]:
        """
        (智慧查詢引擎 v4.1 - 已修正專家搜尋邏輯)
        階段 1: 搜尋 expert 表，優先找 category 匹配的規則
        階段 2: 若失敗，搜尋 general 表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # --- 階段 1: 搜尋「專家規則」 ---
                cursor.execute("SELECT category, name_keywords, disposal_method, tips FROM waste_info_expert WHERE language = ?", (language,))
                expert_rules = cursor.fetchall()
                
                item_to_check = item_name if language == 'zh-TW' else item_name.lower()
                
                # --- vvv 修正邏輯 vvv ---
                
                best_match_rule = None # 用來儲存找到的最佳規則
                
                for rule in expert_rules:
                    rule_category = rule[0] # 這條規則本身的 category (e.g., 'other', 'bulky')
                    db_keywords_str = rule[1]
                    db_keywords = [kw.strip().lower() if language == 'en' else kw.strip() for kw in db_keywords_str.split(',')]
                    
                    found_keyword_match = False
                    for keyword in db_keywords:
                        if item_to_check in keyword:
                            found_keyword_match = True
                            break # 找到關鍵字匹配就跳出內層迴圈
                    
                    if found_keyword_match:
                        # 如果找到的規則 category 與 AI 的 category 相同，這是最佳匹配，直接回傳
                        if rule_category == category:
                            logger.info(f"Exact expert rule found for '{item_name}' (category match: '{category}'), using rule for keywords '{rule[1]}'.")
                            return self._format_rule_response(rule, category) # 使用 AI 的 category
                        
                        # 如果 category 不匹配，先暫存起來，繼續找看看有沒有更好的 (category 匹配的)
                        elif best_match_rule is None:
                             best_match_rule = rule
                
                # 如果迴圈跑完，有找到關鍵字匹配但 category 不符的規則，就使用它 (例如 "汽車" 匹配到玻璃規則)
                if best_match_rule:
                    logger.warning(f"Expert rule found for '{item_name}' but category mismatch (AI: '{category}', Rule: '{best_match_rule[0]}'). Using rule for keywords '{best_match_rule[1]}'.")
                    # 雖然 category 不符，但至少關鍵字對上了，還是用這條規則
                    # 但回傳時，我們仍然使用 AI 判斷的 category ('bulky')
                    return self._format_rule_response(best_match_rule, category) 

                # --- ^^^ 修正邏輯 ^^^ ---


                # --- 階段 2: 搜尋「通用規則」 (後備方案) ---
                # (如果上面完全沒有找到任何關鍵字匹配的專家規則)
                
                logger.info(f"No expert rule found for '{item_name}', falling back to general category '{category}'.")
                
                cursor.execute(
                    "SELECT category, name, disposal_method, tips FROM waste_info_general WHERE category = ? AND language = ? LIMIT 1",
                    (category, language)
                )
                general_rule = cursor.fetchone()

                if general_rule:
                    return self._format_rule_response(general_rule, category)
                
                logger.error(f"CRITICAL: No general rule found for category '{category}' in language '{language}'.")
                return None
                
        except Exception as e:
            logger.error(f"Error getting specific waste info: {e}")
            return None

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
