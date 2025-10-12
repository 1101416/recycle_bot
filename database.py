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
    """插入或更新專家規則 (包含繁中與英文)"""
    cursor = conn.cursor()
    
    default_waste_info = [
        # === 繁體中文規則 ===
        ('other', '衛生紙', '屬於一般垃圾，請直接丟入垃圾桶。', '使用過的衛生紙、餐巾紙因纖維太短且有髒污，不可回收。', 'zh-TW'),
        ('paper', '鋁箔包', '內容物清空並沖洗乾淨，壓扁後投入「紙容器類」回收。', '吸管及封膜屬於塑膠垃圾，請分開回收。', 'zh-TW'),
        ('paper', '紙餐盒', '內容物清空並簡單沖洗，去除殘渣後，投入「紙容器類」回收。', '如果油污太嚴重無法清除，請以一般垃圾丟棄。', 'zh-TW'),
        ('plastic', '塑膠類', '清洗乾淨後投入塑膠類回收桶。', '乾淨的塑膠袋可以回收，但髒污的複合材質塑膠袋(如餅乾袋)不行。', 'zh-TW'),
        ('paper', '紙類', '整理乾淨、去除膠帶釘書針後，投入紙類回收桶。', '此類別指的是一般紙張，非紙容器。請保持乾燥。', 'zh-TW'),
        ('metal', '金屬類', '清洗乾淨後，投入金屬類回收桶。', '尖銳邊緣請小心處理，以免割傷。', 'zh-TW'),
        ('glass', '玻璃類', '清洗乾淨後投入玻璃類回收桶。', '小心破碎，建議用報紙包好再回收。', 'zh-TW'),
        ('other', '其他', '屬於一般垃圾，請直接丟入垃圾桶。', '無法回收或規則未提及的物品皆屬此類。', 'zh-TW'),

        # === 英文規則 ===
        ('other', 'Tissue Paper', 'This is general waste. Please throw it in the regular trash can.', 'Used tissues and napkins are not recyclable due to short fibers and contamination.', 'en'),
        ('paper', 'Tetra Pak', 'Empty and rinse the container, then flatten it and put it in the "Paper Container" recycling bin.', 'Straws and plastic films should be recycled as plastic.', 'en'),
        ('paper', 'Paper Meal Box', 'Empty and briefly rinse to remove food residue, then put it in the "Paper Container" recycling bin.', 'If heavily soiled with grease, dispose of as general waste.', 'en'),
        ('plastic', 'Plastic', 'Rinse clean and place in the plastic recycling bin.', 'Clean plastic bags are recyclable, but dirty composite bags (like snack bags) are not.', 'en'),
        ('paper', 'Paper', 'Tidy up, remove tapes and staples, then place in the paper recycling bin.', 'This refers to general paper, not paper containers. Keep it dry.', 'en'),
        ('metal', 'Metal', 'Rinse clean and place in the metal recycling bin.', 'Be careful with sharp edges.', 'en'),
        ('glass', 'Glass', 'Rinse clean and place in the glass recycling bin.', 'Handle with care. It is recommended to wrap broken glass in newspaper.', 'en'),
        ('other', 'Other', 'This is general waste. Please throw it in the regular trash can.', 'Items that cannot be recycled or are not mentioned in the rules belong here.', 'en'),
    ]

    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_name_lang ON waste_info (name, language)")
        
        # 為了確保更新，我們先刪除所有語言的舊資料再插入
        cursor.execute("DELETE FROM waste_info")
        logger.info("Cleared all old default data.")

        cursor.executemany('''
            INSERT INTO waste_info (category, name, disposal_method, tips, language)
            VALUES (?, ?, ?, ?, ?)
        ''', default_waste_info)
        
        conn.commit()
        logger.info(f"Inserted or updated {cursor.rowcount} expert rules for all languages.")
    except Exception as e:
        logger.error(f"Error inserting default data: {e}")
        raise

if __name__ == "__main__":
    init_database()
    print("Database initialized successfully with updated expert and general rules!")

