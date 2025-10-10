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
            
            conn.commit()
            logger.info("Database tables created or already exist.")
            
            # 插入或更新預設資料
            insert_default_data(conn)
            
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def insert_default_data(conn):
    """插入或更新預設的專家規則"""
    cursor = conn.cursor()
    
    # 專家規則資料庫
    default_waste_info = [
        # --- 修正與新增的規則 ---
        ('other', '衛生紙', '使用過的衛生紙、餐巾紙屬於一般垃圾，請直接丟入垃圾桶。', '衛生紙纖維太短無法回收再利用。除非有標示，否則不可丟入馬桶。', 'zh-TW'),
        ('other', '尿布', '屬於一般垃圾，請妥善包覆後丟入垃圾桶。', '尿布是複合材質，無法回收。', 'zh-TW'),
        ('paper', '鋁箔包', '內容物清空並沖洗乾淨，壓扁後投入「紙容器類」回收。', '吸管及封膜屬於塑膠垃圾，請分開回收。', 'zh-TW'),
        ('paper', '紙杯', '內容物清空並沖洗乾淨，投入「紙容器類」回收。', '杯蓋和吸管請分開回收。', 'zh-TW'),
        ('paper', '紙餐盒', '內容物清空並簡單沖洗，去除殘渣後，投入「紙容器類」回收。', '如果油污太嚴重，請以一般垃圾丟棄。', 'zh-TW'),

        # --- 原有的通用規則 ---
        ('plastic', '塑膠瓶', '清洗乾淨後壓扁，投入塑膠類回收桶。', '記得撕掉標籤和瓶蓋。', 'zh-TW'),
        ('plastic', '塑膠', '清洗乾淨後投入塑膠類回收桶。', '避免使用一次性塑膠袋。', 'zh-TW'),
        ('paper', '紙類', '整理乾淨、去除膠帶釘書針後，投入紙類回收桶。', '避免沾濕或沾到油污。', 'zh-TW'),
        ('metal', '金屬', '清洗乾淨後壓扁，投入金屬類回收桶。', '尖銳邊緣請小心處理。', 'zh-TW'),
        ('glass', '玻璃', '清洗乾淨後投入玻璃類回收桶。', '小心破碎，建議用報紙包好再回收。', 'zh-TW'),
        ('organic', '廚餘', '投入廚餘桶或製作堆肥。', '骨頭、貝殼等硬物通常屬於一般垃圾。', 'zh-TW'),
        ('battery', '電池', '投入電池專用回收桶或交給連鎖超商、量販店回收。', '電池含有害物質，切勿當作一般垃圾丟棄。', 'zh-TW'),
        ('electronics', '電子產品', '送至回收站或交給連鎖電子賣場、超商回收。', '回收前請記得清除個人資料。', 'zh-TW'),
        ('other', '一般垃圾', '請丟入一般垃圾桶。', '無法回收的物品皆屬此類。', 'zh-TW'),
    ]

    try:
        # 使用 INSERT OR IGNORE 避免重複插入，以 name 和 language 作為獨特鍵
        # 為此，我們先在表格上建立一個唯一索引
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_name_lang ON waste_info (name, language)")
        
        cursor.executemany('''
            INSERT OR IGNORE INTO waste_info (category, name, disposal_method, tips, language)
            VALUES (?, ?, ?, ?, ?)
        ''', default_waste_info)
        
        conn.commit()
        logger.info(f"{cursor.rowcount} new default data rows inserted or updated.")
    except Exception as e:
        logger.error(f"Error inserting default data: {e}")
        raise

if __name__ == "__main__":
    init_database()
    print("Database initialized successfully with expert rules!")
