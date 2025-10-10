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
        self.init_database()
    
    def init_database(self):
        """初始化資料庫和表格"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 使用者表格
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        language TEXT DEFAULT 'zh-TW',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        eco_points INTEGER DEFAULT 0
                    )
                ''')
                
                # 分類記錄表格
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS classifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        category TEXT,
                        confidence REAL,
                        image_path TEXT,
                        is_correct BOOLEAN,
                        feedback TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # 垃圾資訊表格
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS waste_info (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT,
                        name TEXT,
                        disposal_method TEXT,
                        tips TEXT,
                        language TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 環保新聞表格
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS news (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        content TEXT,
                        url TEXT,
                        language TEXT,
                        published_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 回收站資訊表格
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS recycling_stations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        address TEXT,
                        latitude REAL,
                        longitude REAL,
                        phone TEXT,
                        hours TEXT,
                        city TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
                # 插入預設垃圾資訊
                self._insert_default_waste_info()
                
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
    
    def _insert_default_waste_info(self):
        """插入預設的垃圾分類資訊"""
        default_waste_info = [
            # 塑膠類
            ('plastic', '塑膠瓶', '清洗乾淨後壓扁，投入塑膠類回收桶', '記得撕掉標籤和瓶蓋', 'zh-TW'),
            ('plastic', '塑膠袋', '清洗乾淨後投入塑膠類回收桶', '避免使用一次性塑膠袋', 'zh-TW'),
            ('plastic', '保麗龍', '清洗乾淨後投入塑膠類回收桶', '大型保麗龍需拆解後回收', 'zh-TW'),
            
            # 紙類
            ('paper', '報紙', '整理後投入紙類回收桶', '避免沾濕或弄髒', 'zh-TW'),
            ('paper', '紙箱', '拆解壓平後投入紙類回收桶', '膠帶需撕除', 'zh-TW'),
            ('paper', '紙杯', '清洗乾淨後投入紙類回收桶', '內層塑膠膜需分離', 'zh-TW'),
            
            # 金屬類
            ('metal', '鋁罐', '清洗乾淨後壓扁，投入金屬類回收桶', '拉環也要回收', 'zh-TW'),
            ('metal', '鐵罐', '清洗乾淨後投入金屬類回收桶', '避免生鏽', 'zh-TW'),
            
            # 玻璃類
            ('glass', '玻璃瓶', '清洗乾淨後投入玻璃類回收桶', '小心破碎，用報紙包好', 'zh-TW'),
            
            # 廚餘
            ('organic', '果皮', '投入廚餘桶或製作堆肥', '避免混入其他垃圾', 'zh-TW'),
            ('organic', '剩菜', '投入廚餘桶', '避免湯汁過多', 'zh-TW'),
            
            # 電池
            ('battery', '乾電池', '投入電池回收桶或超商回收', '不可投入一般垃圾', 'zh-TW'),
            ('battery', '鋰電池', '投入電池回收桶或超商回收', '有起火風險，需特別處理', 'zh-TW'),
            
            # 電子產品
            ('electronics', '手機', '送至回收站或超商回收', '記得清除個人資料', 'zh-TW'),
            ('electronics', '電腦', '送至回收站或超商回收', '硬碟需特別處理', 'zh-TW'),
        ]
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 檢查是否已有資料
                cursor.execute('SELECT COUNT(*) FROM waste_info')
                count = cursor.fetchone()[0]
                
                if count == 0:
                    cursor.executemany('''
                        INSERT INTO waste_info (category, name, disposal_method, tips, language)
                        VALUES (?, ?, ?, ?, ?)
                    ''', default_waste_info)
                    conn.commit()
                    logger.info("Default waste info inserted")
                    
        except Exception as e:
            logger.error(f"Error inserting default waste info: {str(e)}")
    
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
    
    def get_waste_info(self, category: str, language: str = 'zh-TW') -> Dict:
        """取得垃圾分類資訊"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT category, name, disposal_method, tips 
                    FROM waste_info 
                    WHERE category = ? AND language = ?
                    LIMIT 1
                ''', (category, language))
                
                result = cursor.fetchone()
                
                if result:
                    category_name = Config.WASTE_CATEGORIES.get(category, category)
                    return {
                        'category': category,
                        'category_name': category_name,
                        'disposal_method': result[2],
                        'tips': result[3]
                    }
                else:
                    # 如果沒有找到特定語言的資料，使用預設語言
                    cursor.execute('''
                        SELECT category, name, disposal_method, tips 
                        FROM waste_info 
                        WHERE category = ? AND language = 'zh-TW'
                        LIMIT 1
                    ''', (category,))
                    
                    result = cursor.fetchone()
                    if result:
                        category_name = Config.WASTE_CATEGORIES.get(category, category)
                        return {
                            'category': category,
                            'category_name': category_name,
                            'disposal_method': result[2],
                            'tips': result[3]
                        }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting waste info: {str(e)}")
            return None
    
    def search_waste_by_name(self, name: str, language: str = 'zh-TW') -> Optional[Dict]:
        """根據名稱搜尋垃圾資訊"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT category, name, disposal_method, tips 
                    FROM waste_info 
                    WHERE name LIKE ? AND language = ?
                    ORDER BY 
                        CASE WHEN name = ? THEN 1 ELSE 2 END,
                        LENGTH(name) - LENGTH(?)
                    LIMIT 1
                ''', (f'%{name}%', language, name, name))
                
                result = cursor.fetchone()
                
                if result:
                    category_name = Config.WASTE_CATEGORIES.get(result[0], result[0])
                    return {
                        'category': result[0],
                        'category_name': category_name,
                        'disposal_method': result[2],
                        'tips': result[3]
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error searching waste by name: {str(e)}")
            return None
    
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
    
    def add_news(self, title: str, content: str, url: str, language: str = 'zh-TW') -> bool:
        """新增環保新聞"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO news (title, content, url, language, published_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (title, content, url, language))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding news: {str(e)}")
            return False
    
    def get_latest_news(self, language: str = 'zh-TW', limit: int = 5) -> List[Dict]:
        """取得最新環保新聞"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT title, content, url, published_at 
                    FROM news 
                    WHERE language = ? 
                    ORDER BY published_at DESC 
                    LIMIT ?
                ''', (language, limit))
                
                results = cursor.fetchall()
                
                return [
                    {
                        'title': row[0],
                        'content': row[1],
                        'url': row[2],
                        'published_at': row[3]
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Error getting latest news: {str(e)}")
            return []
    
    def add_recycling_station(self, name: str, address: str, latitude: float, 
                            longitude: float, phone: str = None, hours: str = None, 
                            city: str = None) -> bool:
        """新增回收站資訊"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO recycling_stations 
                    (name, address, latitude, longitude, phone, hours, city)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, address, latitude, longitude, phone, hours, city))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding recycling station: {str(e)}")
            return False
    
    def get_nearby_recycling_stations(self, latitude: float, longitude: float, 
                                    radius_km: float = 5.0) -> List[Dict]:
        """取得附近的回收站"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 使用簡單的距離計算（實際應用中可以使用更精確的地理計算）
                cursor.execute('''
                    SELECT name, address, latitude, longitude, phone, hours, city,
                           ((latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?)) as distance_squared
                    FROM recycling_stations 
                    WHERE ((latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?)) <= ?
                    ORDER BY distance_squared
                ''', (latitude, latitude, longitude, longitude, 
                      latitude, latitude, longitude, longitude, radius_km * radius_km))
                
                results = cursor.fetchall()
                
                return [
                    {
                        'name': row[0],
                        'address': row[1],
                        'latitude': row[2],
                        'longitude': row[3],
                        'phone': row[4],
                        'hours': row[5],
                        'city': row[6],
                        'distance': (row[7] ** 0.5) * 111  # 粗略轉換為公里
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Error getting nearby recycling stations: {str(e)}")
            return []
