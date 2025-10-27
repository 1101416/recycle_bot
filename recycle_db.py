# 檔案: recycle_db.py
# (此版本 v4.3 已修正 _format_rule_response 邏輯，優先使用資料庫規則的 category)

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

    # --- vvv 請用這個新版本取代舊的 _format_rule_response vvv ---
    def _format_rule_response(self, rule_tuple: Tuple, ai_category_key: str) -> Optional[Dict]:
        """
        (輔助函式 v2) 將資料庫回傳的 tuple 格式化為 dict
        優先使用 rule_tuple 中儲存的 category。
        """
        if not rule_tuple:
            return None

        # rule_tuple[0] 是資料庫中這條規則實際儲存的 category (e.g., 'ewaste')
        db_category_key = rule_tuple[0]

        # 從 Config 獲取標準的中文名稱 (使用資料庫的 category key)
        category_name_zh = Config.WASTE_CATEGORIES.get(db_category_key, '其他')

        # 如果 AI 的分類和資料庫規則的分類不同，記錄一下
        if ai_category_key != db_category_key:
             logger.warning(f"Category correction: AI suggested '{ai_category_key}', but DB rule is '{db_category_key}'. Using DB category.")

        return {
            'category': db_category_key, # <--- 使用資料庫規則的 category
            'category_name': rule_tuple[1],
            'category_name_zh': category_name_zh,
            'disposal_method': rule_tuple[2],
            'tips': rule_tuple[3]
        }
    # --- ^^^ 請用這個新版本取代舊的 _format_rule_response ^^^ ---

    def get_specific_waste_info(self, category: str, item_name: str, language: str = 'zh-TW') -> Optional[Dict]:
        """
        (智慧查詢引擎 v4.2 - 邏輯不變，僅更新 _format_rule_response 的呼叫)
        階段 1: 搜尋 expert 表，優先找 category 和 keyword 都匹配的規則。
        階段 1.5: 若無完全匹配，再找 keyword 匹配但 category 不符的規則 (作為次級備案)。
        階段 2: 若完全找不到專家規則，才搜尋 general 表。
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # --- 階段 1: 搜尋「專家規則」 ---
                cursor.execute("SELECT category, name_keywords, disposal_method, tips FROM waste_info_expert WHERE language = ?", (language,))
                expert_rules = cursor.fetchall()

                item_to_check = item_name if language == 'zh-TW' else item_name.lower()

                category_mismatch_rule = None # 儲存分類不符的備案

                for rule in expert_rules:
                    rule_category = rule[0] # 資料庫規則的分類
                    db_keywords_str = rule[1]
                    db_keywords = [kw.strip().lower() if language == 'en' else kw.strip() for kw in db_keywords_str.split(',')]

                    found_keyword_match = False
                    for keyword in db_keywords:
                        if item_to_check in keyword:
                            found_keyword_match = True
                            break

                    if found_keyword_match:
                        # 最高優先級：分類和關鍵字都匹配
                        if rule_category == category: # category 是 AI 傳入的分類
                            logger.info(f"Exact expert rule found for '{item_name}' (category match: '{category}'), using rule for keywords '{rule[1]}'.")
                            # 即使匹配，也傳入 AI 的 category 給 _format 供記錄
                            return self._format_rule_response(rule, category)
                        # 次高優先級：關鍵字匹配但分類不符，暫存
                        elif category_mismatch_rule is None:
                             category_mismatch_rule = rule

                # 如果沒有完美匹配，但有分類不符的備案
                if category_mismatch_rule:
                    logger.warning(f"Keyword match found for '{item_name}' but category mismatch (AI: '{category}', Rule: '{category_mismatch_rule[0]}'). Using this rule as fallback: '{category_mismatch_rule[1]}'.")
                    # 將找到的規則 和 AI 的 category 都傳入 format 函式
                    return self._format_rule_response(category_mismatch_rule, category)

                # --- 階段 2: 搜尋「通用規則」 ---
                logger.info(f"No expert rule found for '{item_name}', falling back to general category '{category}'.")

                cursor.execute(
                    "SELECT category, name, disposal_method, tips FROM waste_info_general WHERE category = ? AND language = ? LIMIT 1",
                    (category, language)
                )
                general_rule = cursor.fetchone()

                if general_rule:
                     # 將通用規則 和 AI 的 category 傳入 format 函式
                    return self._format_rule_response(general_rule, category)

                logger.error(f"CRITICAL: No general rule found for category '{category}' in language '{language}'.")
                return None

        except Exception as e:
            logger.error(f"Error getting specific waste info: {e}")
            return None

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
                # 修正：如果找到更精確的專家規則，應該記錄專家規則的分類，而非AI的
                final_category = category # 預設使用 AI 分類
                if is_correct is None and feedback is None: # 代表這是正常分類流程
                    # 嘗試再次搜尋，看是否有更精確的專家規則分類
                    # 注意：這裡假設 item_name 存在於某個地方，或者需要從 classification_result 傳遞過來
                    # 為了簡化，我們先假設 category 是最終的，但未來可以優化這裡
                    pass # 暫時不覆蓋

                cursor.execute('INSERT INTO classifications (user_id, category, confidence, image_path, is_correct, feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (user_id, final_category, confidence, image_path, is_correct, feedback, datetime.now()))
                # 積分計算也應基於最終分類
                if is_correct is None and final_category != 'other' and final_category != 'animal' and final_category != 'money': # 假設非 other/animal/money 就算成功
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
