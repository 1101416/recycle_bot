import sqlite3
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

def init_database():
    """初始化資料庫"""
    try:
        with sqlite3.connect('database.db') as conn:
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
            
            # 系統設定表格
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("Database tables created successfully")
            
            # 插入預設資料
            insert_default_data(cursor)
            
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def insert_default_data(cursor):
    """插入預設資料"""
    try:
        # 檢查是否已有資料
        cursor.execute('SELECT COUNT(*) FROM waste_info')
        count = cursor.fetchone()[0]
        
        if count == 0:
            # 插入預設垃圾分類資訊
            default_waste_info = [
                # 塑膠類 - 繁體中文
                ('plastic', '塑膠瓶', '清洗乾淨後壓扁，投入塑膠類回收桶', '記得撕掉標籤和瓶蓋', 'zh-TW'),
                ('plastic', '塑膠袋', '清洗乾淨後投入塑膠類回收桶', '避免使用一次性塑膠袋', 'zh-TW'),
                ('plastic', '保麗龍', '清洗乾淨後投入塑膠類回收桶', '大型保麗龍需拆解後回收', 'zh-TW'),
                ('plastic', '塑膠容器', '清洗乾淨後投入塑膠類回收桶', '去除食物殘渣', 'zh-TW'),
                
                # 紙類 - 繁體中文
                ('paper', '報紙', '整理後投入紙類回收桶', '避免沾濕或弄髒', 'zh-TW'),
                ('paper', '紙箱', '拆解壓平後投入紙類回收桶', '膠帶需撕除', 'zh-TW'),
                ('paper', '紙杯', '清洗乾淨後投入紙類回收桶', '內層塑膠膜需分離', 'zh-TW'),
                ('paper', '雜誌', '整理後投入紙類回收桶', '保持乾燥', 'zh-TW'),
                
                # 金屬類 - 繁體中文
                ('metal', '鋁罐', '清洗乾淨後壓扁，投入金屬類回收桶', '拉環也要回收', 'zh-TW'),
                ('metal', '鐵罐', '清洗乾淨後投入金屬類回收桶', '避免生鏽', 'zh-TW'),
                ('metal', '鋁箔包', '清洗乾淨後投入金屬類回收桶', '需剪開清洗', 'zh-TW'),
                
                # 玻璃類 - 繁體中文
                ('glass', '玻璃瓶', '清洗乾淨後投入玻璃類回收桶', '小心破碎，用報紙包好', 'zh-TW'),
                ('glass', '玻璃容器', '清洗乾淨後投入玻璃類回收桶', '去除標籤', 'zh-TW'),
                
                # 廚餘 - 繁體中文
                ('organic', '果皮', '投入廚餘桶或製作堆肥', '避免混入其他垃圾', 'zh-TW'),
                ('organic', '剩菜', '投入廚餘桶', '避免湯汁過多', 'zh-TW'),
                ('organic', '茶葉渣', '投入廚餘桶', '可製作堆肥', 'zh-TW'),
                
                # 電池 - 繁體中文
                ('battery', '乾電池', '投入電池回收桶或超商回收', '不可投入一般垃圾', 'zh-TW'),
                ('battery', '鋰電池', '投入電池回收桶或超商回收', '有起火風險，需特別處理', 'zh-TW'),
                ('battery', '鉛蓄電池', '送至回收站或超商回收', '含有重金屬', 'zh-TW'),
                
                # 電子產品 - 繁體中文
                ('electronics', '手機', '送至回收站或超商回收', '記得清除個人資料', 'zh-TW'),
                ('electronics', '電腦', '送至回收站或超商回收', '硬碟需特別處理', 'zh-TW'),
                ('electronics', '家電', '送至回收站或超商回收', '大型家電需預約回收', 'zh-TW'),
                
                # 其他 - 繁體中文
                ('other', '衣物', '捐贈或投入舊衣回收箱', '保持乾淨', 'zh-TW'),
                ('other', '鞋子', '捐贈或投入舊鞋回收箱', '成對回收', 'zh-TW'),
                
                # 英文版本
                ('plastic', 'Plastic Bottle', 'Clean and flatten before recycling', 'Remove labels and caps', 'en'),
                ('paper', 'Newspaper', 'Keep dry and clean for recycling', 'Avoid wetting', 'en'),
                ('metal', 'Aluminum Can', 'Clean and flatten before recycling', 'Remove pull tabs', 'en'),
                ('glass', 'Glass Bottle', 'Clean before recycling', 'Handle with care', 'en'),
                ('organic', 'Food Waste', 'Separate from other waste', 'Compost if possible', 'en'),
                ('battery', 'Battery', 'Take to battery collection point', 'Never throw in regular trash', 'en'),
                ('electronics', 'Electronics', 'Take to e-waste collection point', 'Remove personal data first', 'en'),
                
                # 日文版本
                ('plastic', 'プラスチックボトル', '洗って潰してからリサイクル', 'ラベルとキャップを外す', 'ja'),
                ('paper', '新聞紙', '乾燥した状態でリサイクル', '濡らさないように注意', 'ja'),
                ('metal', 'アルミ缶', '洗って潰してからリサイクル', 'プルトップもリサイクル', 'ja'),
                ('glass', 'ガラス瓶', '洗ってからリサイクル', '割れないよう注意', 'ja'),
                ('organic', '生ゴミ', '他のゴミと分けて処理', '堆肥化も可能', 'ja'),
                ('battery', '電池', '電池回収ボックスへ', '一般ゴミに捨てない', 'ja'),
                ('electronics', '電子機器', '家電回収所へ', '個人データを削除', 'ja'),
                
                # 韓文版本
                ('plastic', '플라스틱 병', '세척 후 압축하여 재활용', '라벨과 뚜껑 제거', 'ko'),
                ('paper', '신문지', '건조한 상태로 재활용', '젖지 않게 주의', 'ko'),
                ('metal', '알루미늄 캔', '세척 후 압축하여 재활용', '풀탭도 재활용', 'ko'),
                ('glass', '유리병', '세척 후 재활용', '깨지지 않게 주의', 'ko'),
                ('organic', '음식물 쓰레기', '다른 쓰레기와 분리', '퇴비화 가능', 'ko'),
                ('battery', '배터리', '배터리 수거함으로', '일반 쓰레기에 버리지 말 것', 'ko'),
                ('electronics', '전자제품', '전자제품 수거소로', '개인정보 삭제 후', 'ko'),
            ]
            
            cursor.executemany('''
                INSERT INTO waste_info (category, name, disposal_method, tips, language)
                VALUES (?, ?, ?, ?, ?)
            ''', default_waste_info)
            
            # 插入預設回收站資訊
            default_stations = [
                ('台北市環保局回收站', '台北市信義區市府路1號', 25.0375, 121.5637, '02-2720-8889', '週一至週五 8:00-17:00', '台北市'),
                ('新北市環保局回收站', '新北市板橋區中山路1段161號', 25.0060, 121.4650, '02-2960-3456', '週一至週五 8:00-17:00', '新北市'),
                ('台中市環保局回收站', '台中市西區民權路99號', 24.1477, 120.6736, '04-2228-9111', '週一至週五 8:00-17:00', '台中市'),
                ('高雄市環保局回收站', '高雄市苓雅區四維三路2號', 22.6273, 120.3014, '07-336-8333', '週一至週五 8:00-17:00', '高雄市'),
            ]
            
            cursor.executemany('''
                INSERT INTO recycling_stations (name, address, latitude, longitude, phone, hours, city)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', default_stations)
            
            # 插入系統設定
            default_settings = [
                ('app_version', '1.0.0', '應用程式版本'),
                ('last_news_update', datetime.now().isoformat(), '最後新聞更新時間'),
                ('total_users', '0', '總使用者數'),
                ('total_classifications', '0', '總分類次數'),
                ('push_enabled', 'true', '推播功能啟用狀態'),
            ]
            
            cursor.executemany('''
                INSERT OR REPLACE INTO system_settings (key, value, description)
                VALUES (?, ?, ?)
            ''', default_settings)
            
            conn.commit()
            logger.info("Default data inserted successfully")
            
    except Exception as e:
        logger.error(f"Error inserting default data: {str(e)}")
        raise

def reset_database():
    """重置資料庫（刪除所有資料）"""
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            
            # 刪除所有表格
            tables = ['users', 'classifications', 'waste_info', 'news', 'recycling_stations', 'system_settings']
            
            for table in tables:
                cursor.execute(f'DROP TABLE IF EXISTS {table}')
            
            conn.commit()
            logger.info("Database reset successfully")
            
            # 重新初始化
            init_database()
            
    except Exception as e:
        logger.error(f"Error resetting database: {str(e)}")
        raise

def backup_database(backup_path: str = None):
    """備份資料庫"""
    try:
        if backup_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f'database_backup_{timestamp}.db'
        
        # 複製資料庫檔案
        import shutil
        shutil.copy2('database.db', backup_path)
        
        logger.info(f"Database backed up to {backup_path}")
        return backup_path
        
    except Exception as e:
        logger.error(f"Error backing up database: {str(e)}")
        return None

def restore_database(backup_path: str):
    """還原資料庫"""
    try:
        import shutil
        shutil.copy2(backup_path, 'database.db')
        
        logger.info(f"Database restored from {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error restoring database: {str(e)}")
        return False

def get_database_stats():
    """取得資料庫統計資訊"""
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # 使用者統計
            cursor.execute('SELECT COUNT(*) FROM users')
            stats['total_users'] = cursor.fetchone()[0]
            
            # 分類記錄統計
            cursor.execute('SELECT COUNT(*) FROM classifications')
            stats['total_classifications'] = cursor.fetchone()[0]
            
            # 垃圾資訊統計
            cursor.execute('SELECT COUNT(*) FROM waste_info')
            stats['total_waste_info'] = cursor.fetchone()[0]
            
            # 新聞統計
            cursor.execute('SELECT COUNT(*) FROM news')
            stats['total_news'] = cursor.fetchone()[0]
            
            # 回收站統計
            cursor.execute('SELECT COUNT(*) FROM recycling_stations')
            stats['total_stations'] = cursor.fetchone()[0]
            
            # 最近活躍使用者
            cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE last_active >= datetime('now', '-7 days')
            ''')
            stats['active_users_7days'] = cursor.fetchone()[0]
            
            # 今日分類次數
            cursor.execute('''
                SELECT COUNT(*) FROM classifications 
                WHERE created_at >= date('now')
            ''')
            stats['classifications_today'] = cursor.fetchone()[0]
            
            return stats
            
    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}")
        return {}

if __name__ == "__main__":
    # 如果直接執行此檔案，則初始化資料庫
    init_database()
    print("Database initialized successfully!")
