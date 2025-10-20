# database.py
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
DB_PATH = 'database.db'

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """初始化資料庫並寫入預設回收規則（會覆寫舊規則）"""
    logging.basicConfig(level=logging.INFO)
    try:
        with _get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    language TEXT DEFAULT 'zh-TW',
                    created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                    last_active TIMESTAMP DEFAULT (datetime('now','localtime')),
                    eco_points INTEGER DEFAULT 0
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS classifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    category TEXT,
                    confidence REAL,
                    image_path TEXT,
                    is_correct BOOLEAN,
                    feedback TEXT,
                    created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS waste_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    name TEXT,
                    disposal_method TEXT,
                    tips TEXT,
                    language TEXT,
                    created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
                )
            ''')

            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_waste_name_lang ON waste_info (name, language)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_waste_category_lang ON waste_info (category, language)")

            conn.commit()
            logger.info("Database tables created or already exist.")

            # 插入預設資料（覆寫）
            insert_default_data(conn)

    except Exception as e:
        logger.exception(f"Error initializing database: {e}")
        raise

def insert_default_data(conn=None):
    """
    插入詳細預設回收規則（繁中 + 英文）。
    注意：此函式會清空 waste_info 再寫入最新規則（以 Config.WASTE_CATEGORIES 對應的類別為主）。
    """
    close_conn = False
    if conn is None:
        conn = _get_conn()
        close_conn = True

    cursor = conn.cursor()

    # -------------------------
    # 詳細規則 - 中文（zh-TW）
    # name 欄為逗號分隔的 keyword / 同義詞（程式比對時會拆開）
    # -------------------------
    default_waste_info = [
        # --- 廚餘 (food) ---
        ('food', '廚餘,剩菜,剩飯,果皮,蔬菜梗,茶葉渣,咖啡渣,廚房殘渣', 
         '請投入廚餘桶或使用社區指定可分解廚餘袋，瀝乾湯汁並去除塑膠包材。', 
         '不可混入塑膠、玻璃、金屬或一次性餐具；骨頭、殼類視當地規定處理。', 'zh-TW'),

        # --- 紙類 (paper) ---
        ('paper', '報紙,書籍,紙張,筆記紙,信封,廣告單,紙箱', 
         '整理乾淨、去除膠帶、釘書針，平鋪或綑綁後投入紙類回收。', 
         '沾油或濕潤的紙張視為一般垃圾。', 'zh-TW'),

        ('paper', '紙容器,利樂包,牛奶盒,豆漿盒,飲料紙盒,紙杯', 
         '內容物倒空並沖洗（簡單沖洗即可），壓扁後投入紙容器類回收。', 
         '拆除塑膠吸管與封膜，塑膠部分分開回收。', 'zh-TW'),

        # --- 塑膠 (plastic) ---
        ('plastic', '塑膠瓶,飲料瓶,PET瓶,塑膠容器,保特瓶', 
         '內容物倒空並沖洗乾淨，瓶身壓扁後投入塑膠回收；瓶蓋依當地規定處理。', 
         '複合材質（餅乾袋、洋芋片袋）通常不可回收。', 'zh-TW'),

        ('plastic', '塑膠袋,塑膠薄膜,保鮮膜,購物袋', 
         '乾淨且單一材質的塑膠袋可回收於塑膠薄膜回收點；髒污或多層材質請以一般垃圾處理。', 
         '切勿將塑膠薄膜混入紙類回收。', 'zh-TW'),

        # --- 金屬 (metal) ---
        ('metal', '鐵罐,鋁罐,鋁箔,金屬瓶蓋,金屬餐具,鋁製容器', 
         '沖洗乾淨後投入金屬回收。', 
         '大型油桶或污染嚴重之金屬容器需特殊處理。', 'zh-TW'),

        # --- 玻璃 (glass) ---
        ('glass', '玻璃瓶,酒瓶,玻璃罐,醬油瓶', 
         '沖洗乾淨後投入玻璃回收；破裂玻璃請以報紙包好再丟棄並標示破碎。', 
         '鏡子、燈罩、耐熱玻璃（如燒杯）常不接受，依當地規定。', 'zh-TW'),

        # --- 紡織品 (textile) ---
        ('textile', '衣物,舊衣,被單,毛巾,布料,鞋子', 
         '可捐贈可使用之衣物或放入指定回收箱；污損嚴重者視為一般垃圾或大型廢棄物處理。', 
         '請保持乾燥且清潔再捐贈。', 'zh-TW'),

        # --- 電子廢棄物 (ewaste) ---
        ('ewaste', '電池,鋰電池,鹼性電池,手機,電腦,平板,充電器,電視,冰箱,家電', 
         '小型電池投入回收箱；手機、電腦與家電送至資源回收或家電門市回收服務。', 
         '鋰電池需絕緣包裝，切勿丟入一般垃圾或焚化。', 'zh-TW'),

        # --- 有害垃圾 (hazard) ---
        ('hazard', '油漆,溶劑,農藥,藥品,過期藥品,汞溫度計,節能燈管,化學品', 
         '列為有害廢棄物，請送至指定回收活動或有害廢棄物收集點。', 
         '藥品請交藥局或衛生單位回收；節能燈管含汞，勿摔破。', 'zh-TW'),

        ('hazard', '香水,香氛,香水瓶,香水噴霧', 
         '含揮發性有機溶劑，視為有害/特殊化學製劑，建議帶至有害廢棄物回收點處理。', 
         '剩餘液體勿倒入水槽，可以吸附後回收或交由專門單位處理。', 'zh-TW'),

        ('hazard', '噴霧罐,氣霧罐,含壓罐', 
         '屬增壓容器，有爆裂或易燃風險，請送至有害廢棄物回收或指定回收站。', 
         '切勿刺破或焚燒。', 'zh-TW'),

        # --- 大型廢棄物 (bulky) ---
        ('bulky', '家具,床墊,沙發,大型家電,汽車,轎車,機車,自行車', 
         '屬大型廢棄物，需依當地清潔隊或資源回收中心預約回收或報廢流程。', 
         '汽車與機車含油品與電池，需由專業單位拆解處理。', 'zh-TW'),

        # --- 其他/一般垃圾 (other) ---
        ('other', '一般垃圾,其他,髒汙物,衛生紙,紙尿褲,濕紙巾,棉花棒', 
         '請丟入一般垃圾袋並妥善包裝，臭味大或滲漏請密封處理。', 
         '衛生用品與被污染紙類屬一般垃圾。', 'zh-TW'),

        # --- 特殊項目補充 ---
        ('other', '保麗龍,發泡聚苯乙烯,泡棉', 
         '若無法清潔或回收點不收，請以一般垃圾處理；乾淨可回收者送指定回收點。', 
         '食物沾染之保麗龍不可回收。', 'zh-TW'),

        ('other', '食用油,廚房油', 
         '冷卻後以密封容器回收或送至資源回收站；切勿倒入水槽。', 
         '少量油可用吸油紙吸乾後一般垃圾處理（視在地規定）。', 'zh-TW'),

        ('other', '餅乾袋,真空包裝,複合包材,多層包裝', 
         '多層複合材質通常不可回收，請以一般垃圾處理或依地方分離規範。', 
         '若可分離成單一材質才可依材質分類回收。', 'zh-TW'),

        ('metal', '車用電池,鉛酸電池,汽車電池', 
         '含危險化學與重金屬，應送至電池回收或有害廢棄物處理。', 
         '交由車行或資源回收業者處理，勿丟入一般垃圾。', 'zh-TW'),

        # -------------------------
        # English entries (en) — mirror of above for bilingual support
        # -------------------------
        ('food', 'food waste,leftovers,fruit peels,vegetable scraps,tea leaves,coffee grounds',
         'Put into designated food waste bin or compost collection. Drain liquid and remove packaging.', 'Do not mix with plastics, metals, glass.', 'en'),

        ('paper', 'newspaper,books,office paper,envelopes,cardboard',
         'Flatten and place in paper recycling; remove tape/staples.', 'Do not include heavily soiled paper.', 'en'),

        ('paper', 'tetra pak,beverage carton,milk carton',
         'Empty and rinse, flatten and put in paper-container recycling.', 'Remove straws and plastic films.', 'en'),

        ('plastic', 'plastic bottle,plastic container,PET bottle',
         'Rinse and recycle with plastics; remove caps per local guidelines.', '', 'en'),

        ('plastic', 'plastic bag,cling film,plastic film',
         'Clean single-material plastic films may be recycled at drop-off points; dirty/multi-layer dispose as general waste.', '', 'en'),

        ('metal', 'metal can,aluminum can,metal lid,metal utensils',
         'Rinse and put in metal recycling.', '', 'en'),

        ('glass', 'glass bottle,glass jar,jar,wine bottle',
         'Rinse and put in glass recycling; wrap broken glass before disposal.', '', 'en'),

        ('textile', 'clothes,bedding,towels,shoes',
         'Donate usable textiles or place in textile collection bins.', '', 'en'),

        ('ewaste', 'battery,lithium battery,phone,computer,appliance',
         'Take to e-waste collection points; lithium batteries must be insulated.', '', 'en'),

        ('hazard', 'paint,solvent,pesticide,expired medicine,mercury,fluorescent tube',
         'Deliver to hazardous waste collection centers.', 'Tape battery terminals to avoid short-circuiting.', 'en'),

        ('hazard', 'perfume,fragrance,perfume bottle,aerosol perfume',
         'Contains volatile organic solvents — bring to hazardous collection events.', '', 'en'),

        ('hazard', 'aerosol,spray can,aerosol can',
         'Pressurized container; return to hazardous waste points. Do not puncture or incinerate.', '', 'en'),

        ('bulky', 'furniture,mattress,sofa,large appliance,car,vehicle,bicycle',
         'Requires bulky waste pickup or drop-off at designated centers.', 'Vehicles must be decommissioned by authorized services; fuel and batteries require special handling.', 'en'),

        ('other', 'general waste,other,contaminated waste,tissue,diaper,wet wipes',
         'Put into regular trash and seal if smelly or wet.', '', 'en'),
    ]

    try:
        cursor.execute("DELETE FROM waste_info")
        now = datetime.now().isoformat()
        records = []
        for c, name, method, tips, lang in default_waste_info:
            records.append((c, name, method, tips, lang, now))
        cursor.executemany('''
            INSERT INTO waste_info (category, name, disposal_method, tips, language, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', records)
        conn.commit()
        logger.info(f"Inserted {len(records)} default waste rules.")
    except Exception as e:
        logger.exception(f"Error inserting default data: {e}")
        raise
    finally:
        if close_conn:
            conn.close()

if __name__ == "__main__":
    init_database()
    print("Database initialized successfully (detailed waste rules inserted).")
