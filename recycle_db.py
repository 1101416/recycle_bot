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
        """(新版通用查詢) 依據 category，精準查詢其通用的處理規則"""
        try:
            # 從 Config 取得該 category 的中文名稱，作為查詢的 key
            general_item_name = Config.WASTE_CATEGORIES.get(category)
            if not general_item_name:
                return None

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 查詢 category 和 name 都符合的通用規則
                cursor.execute(
                    "SELECT category, name, disposal_method, tips FROM waste_info WHERE category = ? AND name = ? AND language = ? LIMIT 1",
                    (category, general_item_name, 'zh-TW')
                )
                result = cursor.fetchone()
                
                if result:
                    return {
                        'category': result[0],
                        'category_name': result[1],
                        'disposal_method': result[2],
                        'tips': result[3]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting general waste info for category '{category}': {e}")
            return None

    def get_specific_waste_info(self, category: str, item_name: str, language: str = 'zh-TW') -> Optional[Dict]:
        """(智慧查詢) 依據品項名稱取得最精確的資訊，若無則回退到通用類別"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT category, name, disposal_method, tips FROM waste_info WHERE language = ?", ('zh-TW',))
                all_rules = cursor.fetchall()

                best_match = None
                for rule in all_rules:
                    db_keyword = rule[1]
                    # 排除通用規則本身，只比對專家規則
                    if db_keyword in Config.WASTE_CATEGORIES.values():
                        continue
                    
                    if db_keyword in item_name:
                        best_match = rule
                        break

                if best_match:
                    logger.info(f"Expert rule found for '{item_name}', using rule for '{best_match[1]}'.")
                    correct_category = best_match[0]
                    category_name_zh = Config.WASTE_CATEGORIES.get(correct_category, correct_category)
                    
                    return {
                        'category': correct_category,
                        'category_name': category_name_zh,
                        'disposal_method': best_match[2],
                        'tips': best_match[3]
                    }
                
                logger.info(f"No expert rule found for '{item_name}', falling back to general category '{category}'.")
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
                    cursor.execute('INSERT INTO users (user_id, language) VALUES (?, ?)', (user_id, language))
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
                cursor.execute('INSERT INTO classifications (user_id, category, confidence, image_path, is_correct, feedback) VALUES (?, ?, ?, ?, ?, ?)', (user_id, category, confidence, image_path, is_correct, feedback))
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
