# 檔案: recycle_db.py
# (此版本已優化，使用兩個資料表進行搜尋)

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
    
    # --- vvv 舊的 get_waste_info 函式已被刪除 vvv ---
    # (因為它的邏輯已合併到 get_specific_waste_info 中)
    # --- ^^^ 舊的 get_waste_info 函式已被刪除 ^^^ ---

    def _format_rule_response(self, rule_tuple: Tuple, category_key: str) -> Optional[Dict]:
        """(輔助函式) 將資料庫回傳的 tuple 格式化為 dict"""
        if not rule_tuple:
            return None
        
        # 從 Config 獲取標準的中文名稱 (e.g., 'ewaste' -> '電子廢棄物')
        category_name_zh = Config.WASTE_CATEGORIES.get(category_key, '其他')
        
        return {
            'category': rule_tuple[0],
            'category_name': rule_tuple[1],      # 這是規則中的名稱 (e.g., "雜誌,影印紙..." 或 "紙類")
            'category_name_zh': category_name_zh,  # 這是分類的標準名稱 (e.g., "紙類")
            'disposal_method': rule_tuple[2],
            'tips': rule_tuple[3]
        }

    def get_specific_waste_info(self, category: str, item_name: str, language: str = 'zh-TW') -> Optional[Dict]:
        """
        (智慧查詢引擎 v4.0 - 已優化)
        階段 1: 搜尋 `waste_info_expert` 資料表
        階段 2: 若失敗，搜尋 `waste_info_general` 資料表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # --- 階段 1: 搜尋「專家規則」 ---
                
                # 僅撈出專家規則
                cursor.execute("SELECT category, name_keywords, disposal_method, tips FROM waste_info_expert WHERE language = ?", (language,))
                expert_rules = cursor.fetchall()
                
                item_to_check = item_name if language == 'zh-TW' else item_name.lower()
                
                for rule in expert_rules:
                    db_keywords_str = rule[1]
                    db_keywords = [kw.strip().lower() if language == 'en' else kw.strip() for kw in db_keywords_str.split(',')]
                    
                    for keyword in db_keywords:
                        if item_to_check in keyword:
                            logger.info(f"Expert rule found for '{item_name}', using rule for keywords '{rule[1]}'.")
                            # 找到專家規則，格式化並回傳
                            return self._format_rule_response(rule, rule[0]) # rule[0] 是該規則的 category

                # --- 階段 2: 搜尋「通用規則」 (後備方案) ---
                
                logger.info(f"No expert rule found for '{item_name}', falling back to general category '{category}'.")
                
                # 直接使用 AI 提供的 category 進行一次高效率的通用規則查詢
                cursor.execute(
                    "SELECT category, name, disposal_method, tips FROM waste_info_general WHERE category = ? AND language = ? LIMIT 1",
                    (category, language)
                )
                general_rule = cursor.fetchone()

                if general_rule:
                    # 找到通用規則，格式化並回傳
                    return self._format_rule_response(general_rule, category)
                
                # 如果連通用規則都找不到 (理論上不該發生)
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
