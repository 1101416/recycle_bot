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
        # 移除舊的初始化，讓主程式決定何時初始化
    
    def get_waste_info(self, category: str, language: str = 'zh-TW') -> Dict:
        """(舊方法) 取得通用的垃圾分類資訊"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 優先查詢 'zh-TW'
                cursor.execute("SELECT category, name, disposal_method, tips FROM waste_info WHERE category = ? AND language = ? LIMIT 1", (category, 'zh-TW'))
                result = cursor.fetchone()
                
                if result:
                    category_name_zh = Config.WASTE_CATEGORIES.get(category, category)
                    return {'category': category, 'category_name': category_name_zh, 'disposal_method': result[2], 'tips': result[3]}
                return None
        except Exception as e:
            logger.error(f"Error getting waste info: {e}")
            return None

    def get_specific_waste_info(self, category: str, item_name: str, language: str = 'zh-TW') -> Dict:
        """(新方法) 依據品項名稱取得最精確的資訊，若無則回退到通用類別"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 1. 嘗試用 item_name 進行模糊查詢，尋找最精確的規則
                cursor.execute("SELECT category, name, disposal_method, tips FROM waste_info WHERE ? LIKE '%' || name || '%' AND language = ? LIMIT 1", (item_name, 'zh-TW'))
                result = cursor.fetchone()

                # 2. 如果找不到精確規則，則使用通用類別查詢 (回退)
                if not result:
                    return self.get_waste_info(category, language)

                # 如果找到了精確規則 (例如'衛生紙'被歸類為'other')，使用資料庫中定義的正確分類
                correct_category = result[0]
                category_name_zh = Config.WASTE_CATEGORIES.get(correct_category, correct_category)
                
                return {
                    'category': correct_category,
                    'category_name': category_name_zh,
                    'disposal_method': result[2],
                    'tips': result[3]
                }
        except Exception as e:
            logger.error(f"Error getting specific waste info: {e}")
            # 發生錯誤時，安全地回退到通用查詢
            return self.get_waste_info(category, language)

    # --- 以下為使用者資料相關函式，維持不變 ---
    # ... (此處省略 get_or_create_user, get_user_language 等函式，它們維持原樣)
    def get_or_create_user(self, user_id: str, language: str = 'zh-TW') -> Dict:
        """取得或創建使用者"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 檢查使用者是否存在
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                user = cursor.fetchone()
                
                if user:
                    # 更新最後活躍時間
                    cursor.execute('''
                        UPDATE users 
                        SET last_active = CURRENT_TIMESTAMP 
                        WHERE user_id = ?
                    ''', (user_id,))
                    conn.commit()
                    
                    return {
                        'user_id': user[0],
                        'language': user[1],
                        'created_at': user[2],
                        'last_active': user[3],
                        'eco_points': user[4]
                    }
                else:
                    # 創建新使用者
                    cursor.execute('''
                        INSERT INTO users (user_id, language)
                        VALUES (?, ?)
                    ''', (user_id, language))
                    conn.commit()
                    
                    return {
                        'user_id': user_id,
                        'language': language,
                        'created_at': datetime.now().isoformat(),
                        'last_active': datetime.now().isoformat(),
                        'eco_points': 0
                    }
                    
        except Exception as e:
            logger.error(f"Error getting/creating user: {str(e)}")
            return None
    
    def get_user_language(self, user_id: str) -> Optional[str]:
        """取得使用者語言偏好"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
                
        except Exception as e:
            logger.error(f"Error getting user language: {str(e)}")
            return None
    
    def update_user_language(self, user_id: str, language: str) -> bool:
        """更新使用者語言偏好"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET language = ?, last_active = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                ''', (language, user_id))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error updating user language: {str(e)}")
            return False
    
    def record_classification(self, user_id: str, category: str, confidence: float, 
                            image_path: str = None, is_correct: bool = None, 
                            feedback: str = None) -> bool:
        """記錄分類結果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO classifications 
                    (user_id, category, confidence, image_path, is_correct, feedback)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, category, confidence, image_path, is_correct, feedback))
                
                # 如果分類正確，增加環保積分
                if is_correct:
                    cursor.execute('''
                        UPDATE users 
                        SET eco_points = eco_points + 1 
                        WHERE user_id = ?
                    ''', (user_id,))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error recording classification: {str(e)}")
            return False
    
    def get_user_stats(self, user_id: str) -> Dict:
        """取得使用者統計資訊"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 總分類次數
                cursor.execute('''
                    SELECT COUNT(*) FROM classifications 
                    WHERE user_id = ?
                ''', (user_id,))
                total_classifications = cursor.fetchone()[0]
                
                # 正確分類次數
                cursor.execute('''
                    SELECT COUNT(*) FROM classifications 
                    WHERE user_id = ? AND is_correct = 1
                ''', (user_id,))
                correct_classifications = cursor.fetchone()[0]
                
                # 正確分類率
                accuracy_rate = (correct_classifications / total_classifications * 100) if total_classifications > 0 else 0
                
                # 最常分類的類別
                cursor.execute('''
                    SELECT category, COUNT(*) as count 
                    FROM classifications 
                    WHERE user_id = ? 
                    GROUP BY category 
                    ORDER BY count DESC 
                    LIMIT 1
                ''', (user_id,))
                most_common = cursor.fetchone()
                most_common_category = most_common[0] if most_common else '無'
                
                # 環保積分
                cursor.execute('SELECT eco_points FROM users WHERE user_id = ?', (user_id,))
                eco_points = cursor.fetchone()[0] if cursor.fetchone() else 0
                
                return {
                    'total_classifications': total_classifications,
                    'correct_classifications': correct_classifications,
                    'accuracy_rate': accuracy_rate,
                    'most_common_category': most_common_category,
                    'eco_points': eco_points
                }
                
        except Exception as e:
            logger.error(f"Error getting user stats: {str(e)}")
            return {
                'total_classifications': 0,
                'correct_classifications': 0,
                'accuracy_rate': 0,
                'most_common_category': '無',
                'eco_points': 0
            }
