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
            
            # 建立表格 (此處省略，維持原樣)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, language TEXT DEFAULT 'zh-TW', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP, eco_points INTEGER DEFAULT 0)
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS classifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, category TEXT, confidence REAL, image_path TEXT,
                    is_correct BOOLEAN, feedback TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id))
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS waste_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, name TEXT, disposal_method TEXT,
                    tips TEXT, language TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
            ''')
            
            conn.commit()
            logger.info("Database tables created or already exist.")
            
            # 插入或更新預設資料
            insert_default_data(conn)
            
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def insert_default_data(conn):
    """插入或更新從PDF整理的專家規則，並包含通用規則"""
    cursor = conn.cursor()
    
    default_waste_info = [
        # === 專家規則 (Specific Items) ===
        ('other', '衛生紙', '屬於一般垃圾，請直接丟入垃圾桶。', '使用過的衛生紙、餐巾紙因纖維太短且有髒污，不可回收。', 'zh-TW'),
        ('other', '紙尿褲', '屬於一般垃圾，請妥善包覆後丟入垃圾桶。', '紙尿褲是複合材質，無法回收。', 'zh-TW'),
        ('other', '感熱紙', '屬於一般垃圾，請直接丟入垃圾桶。', '例如電子發票、傳真紙、收據等，含有化學物質無法回收。', 'zh-TW'),
        ('other', '髒污的紙張', '屬於一般垃圾，請直接丟入垃圾桶。', '沾有油漆、油污或寵物排泄物的紙張不可回收。', 'zh-TW'),
        
        ('paper', '鋁箔包', '內容物清空並沖洗乾淨，壓扁後投入「紙容器類」回收。', '吸管及封膜屬於塑膠垃圾，請分開回收。', 'zh-TW'),
        ('paper', '紙盒包', '內容物清空並沖洗乾淨，壓扁後投入「紙容器類」回收。', '例如牛奶盒、豆漿盒等新鮮屋包裝。', 'zh-TW'),
        ('paper', '紙杯', '內容物清空並沖洗乾淨，投入「紙容器類」回收。', '杯蓋和吸管請分開回收。', 'zh-TW'),
        ('paper', '紙餐盒', '內容物清空並簡單沖洗，去除殘渣後，投入「紙容器類」回收。', '如果油污太嚴重無法清除，請以一般垃圾丟棄。', 'zh-TW'),

        # === 通用規則 (General Categories) - 使用中文類別名稱作為 key ===
        ('plastic', '塑膠類', '清洗乾淨後投入塑膠類回收桶。', '乾淨的塑膠袋可以回收，但髒污的複合材質塑膠袋(如餅乾袋)不行。', 'zh-TW'),
        ('paper', '紙類', '整理乾淨、去除膠帶釘書針後，投入紙類回收桶。', '請保持乾燥，避免沾濕或沾到油污。', 'zh-TW'),
        ('metal', '金屬類', '清洗乾淨後，投入金屬類回收桶。', '尖銳邊緣請小心處理，以免割傷。', 'zh-TW'),
        ('glass', '玻璃類', '清洗乾淨後投入玻璃類回收桶。', '小心破碎，建議用報紙包好再回收。', 'zh-TW'),
        ('organic', '廚餘', '投入廚餘桶或製作堆肥。', '骨頭、貝殼、果核等硬物通常屬於一般垃圾。', 'zh-TW'),
        ('battery', '電池', '投入電池專用回收桶或交給連鎖超商、量販店回收。', '電池含有害物質，切勿當作一般垃圾丟棄。', 'zh-TW'),
        ('electronics', '電子產品', '送至回收站或交給連鎖電子賣場、超商回收。', '回收前請記得清除個人資料。', 'zh-TW'),
        ('other', '其他', '屬於一般垃圾，請直接丟入垃圾桶。', '無法回收或規則未提及的物品皆屬此類。', 'zh-TW'),
    ]

    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_name_lang ON waste_info (name, language)")
        
        # 為了確保更新，我們先刪除舊有資料再插入
        cursor.execute("DELETE FROM waste_info WHERE language = 'zh-TW'")
        logger.info("Cleared old default data for 'zh-TW'.")

        cursor.executemany('''
            INSERT INTO waste_info (category, name, disposal_method, tips, language)
            VALUES (?, ?, ?, ?, ?)
        ''', default_waste_info)
        
        conn.commit()
        logger.info(f"Inserted or updated {cursor.rowcount} expert rules.")
    except Exception as e:
        logger.error(f"Error inserting default data: {e}")
        raise

if __name__ == "__main__":
    init_database()
    print("Database initialized successfully with updated expert and general rules!")
