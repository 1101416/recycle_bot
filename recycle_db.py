# 檔案: recycle_db.py
# (此版本 v6.1 已修正為「專家規則優先」邏輯)

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

    # _format_rule_response 函式保持 v4.3/v5.0 的邏輯不變
    # (它會優先使用 rule_tuple[0] (資料庫分類) 作為最終分類)
    def _format_rule_response(self, rule_tuple: Tuple, ai_category_key: str) -> Optional[Dict]:
        """(輔助函式 v3) 將資料庫回傳的 tuple 格式化為 dict"""
        if not rule_tuple: return None
        db_category_key = rule_tuple[0]
        category_name_zh = Config.WASTE_CATEGORIES.get(db_category_key, '其他')
        if ai_category_key != db_category_key:
             logger.warning(f"Category correction: AI suggested '{ai_category_key}', but DB rule is '{db_category_key}'. Using DB category.")
        return {
            'category': db_category_key,
            'category_name': rule_tuple[1],
            'category_name_zh': category_name_zh,
            'disposal_method': rule_tuple[2],
            'tips': rule_tuple[3]
        }

    def log_unresolved_item(self, ai_category: str, item_zh: str, item_en: str, language: str):
        """將 AI 分類後但在專家規則中找不到的項目記錄到資料庫。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO unresolved_items (ai_category, item_name_zh, item_name_en, language) VALUES (?, ?, ?, ?)",
                    (ai_category, item_zh, item_en, language)
                )
                conn.commit()
                logger.info(f"Logged unresolved item: {ai_category} / {item_zh} / {item_en}")
        except Exception as e:
            logger.error(f"Failed to log unresolved item to DB: {e}")

    # --- vvv 請用這個「專家優先 v6.1」的版本取代舊的 get_specific_waste_info vvv ---
    def get_specific_waste_info(self, ai_classification_result: dict, language: str = 'zh-TW') -> Optional[Dict]:
        """
        (智慧查詢引擎 v6.1 - 專家規則優先邏輯)
        階段 1: (忽略 AI category) 搜尋 expert 表，尋找第一個匹配 keyword 的規則。
        階段 2: 若失敗，記錄到 unresolved_items，然後 (使用 AI category) 搜尋 general 表。
        階段 3: 若皆失敗，回傳 None。
        """
        
        # 1. 從 AI 結果中提取所需資訊
        ai_category = ai_classification_result.get('category', 'other')
        item_zh = ai_classification_result.get('item_name_zh', '')
        item_en = ai_classification_result.get('item_name_en', '')
        
        item_to_check = item_zh if language == 'zh-TW' else item_en.lower()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # --- 階段 1: 搜尋「專家規則」(關鍵字優先) ---
                # (不再於 SQL 中篩選 category)
                cursor.execute(
                    "SELECT category, name_keywords, disposal_method, tips FROM waste_info_expert WHERE language = ?",
                    (language,) 
                )
                expert_rules = cursor.fetchall()

                for rule in expert_rules:
                    db_keywords_str = rule[1]
                    db_keywords = [kw.strip().lower() if language == 'en' else kw.strip() for kw in db_keywords_str.split(',')]

                    for keyword in db_keywords:
                        if item_to_check in keyword:
                            # 找到了！ (例如 '鍵盤' in '...鍵盤...')
                            logger.info(f"Expert rule keyword match found for '{item_to_check}', using rule for keywords '{rule[1]}'.")
                            # (呼叫 _format_rule_response 會自動處理 AI 分類錯誤的警告)
                            return self._format_rule_response(rule, ai_category)

                # --- 階段 2: 搜尋「通用規則」 (後備方案) ---
                
                logger.info(f"No expert rule found for '{item_to_check}', falling back to general category '{ai_category}'.")
                
                # 記錄這個「專家規則缺口」
                if ai_category not in ['chat', 'other']:
                    self.log_unresolved_item(ai_category, item_zh, item_en, language)

                cursor.execute(
                    "SELECT category, name, disposal_method, tips FROM waste_info_general WHERE category = ? AND language = ? LIMIT 1",
                    (ai_category, language)
                )
                general_rule = cursor.fetchone()

                if general_rule:
                    return self._format_rule_response(general_rule, ai_category)

                # --- 階段 3: 最終失敗 ---
                logger.error(f"CRITICAL: No general rule found for category '{ai_category}' in language '{language}'. (Final fallback)")
                return None

        except Exception as e:
            logger.error(f"Error getting specific waste info: {e}")
            return None
    # --- ^^^ 請用这个「專家優先 v6.1」的版本取代舊的 get_specific_waste_info ^^^ ---


    # --- 以下為使用者資料相關函式，維持不變 ---
    # ... (get_or_create_user, get_user_language, etc. 保持不變) ...
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
                final_category = category
                cursor.execute('INSERT INTO classifications (user_id, category, confidence, image_path, is_correct, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (user_id, final_category, confidence, image_path, is_correct, feedback, datetime.now()))
                if is_correct is None and final_category not in ['other', 'animal', 'money', 'chat']:
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
