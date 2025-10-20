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
            
            # 建立表格 (維持原樣)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, language TEXT, created_at TIMESTAMP,
                    last_active TIMESTAMP, eco_points INTEGER)
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS classifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, category TEXT, confidence REAL,
                    image_path TEXT, is_correct BOOLEAN, feedback TEXT, created_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id))
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS waste_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, name TEXT, disposal_method TEXT,
                    tips TEXT, language TEXT, created_at TIMESTAMP)
            ''')
            
            conn.commit()
            logger.info("Database tables created or already exist.")
            
            # 插入或更新您提供的最新資料
            insert_default_data(conn)
            
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def insert_default_data(conn):
    """(最新版) 插入或更新您提供的完整回收規則"""
    cursor = conn.cursor()
    
    # 使用您提供的最新回收規則
    default_waste_info = [
        # === 繁體中文規則 (zh-TW) ===
        ('food', '廚餘,剩菜,剩飯,果皮,蔬菜梗,茶葉渣,咖啡渣', '請於廚餘桶或社區廚餘回收袋投入，盡量瀝乾湯汁、去除塑膠包材後丟棄。', '不可混入塑膠、金屬、玻璃或一次性餐具；肉骨頭視當地規定，部分採一般垃圾處理。', 'zh-TW'),
        ('food', '廚餘袋,廚餘盒', '請使用可分解或社區指定之廚餘袋包裝，密封後投入廚餘回收。', '若無廚餘回收，應以一般垃圾處理並避免滲漏。', 'zh-TW'),
        ('paper', '紙容器,利樂包,牛奶盒,豆漿盒,飲料紙盒', '內容物倒空並沖洗乾淨，壓扁後投入「紙容器類」回收。', '吸管、塑膠封膜及內襯請拆下，吸管屬塑膠回收（若能分離）。', 'zh-TW'),
        ('paper', '報紙,書籍,筆記紙,信封,廣告單,紙箱', '請整理乾淨、去除膠帶與釘書針，分類平鋪或綑綁後投入紙類回收。', '被油污、食物殘渣污染的紙張請以一般垃圾處理。', 'zh-TW'),
        ('plastic', '塑膠瓶,飲料瓶,塑膠容器,保麗龍餐盒(乾淨)', '沖洗乾淨並壓扁（若適用），去除瓶蓋和標籤（視當地規定）後投入塑膠回收。', '複合材質塑膠袋（餅乾袋、真空包）若無法清洗或分解則不可回收。', 'zh-TW'),
        ('other', '塑膠袋,購物袋,保鮮膜,塑膠薄膜', '乾淨且單一材質的塑膠袋可回收（視各地回收點），但髒污或複合材質請以一般垃圾處理。', '請勿將塑膠薄膜混入紙類或其他回收物，以免污染。', 'zh-TW'),
        ('metal', '鐵罐,鋁罐,金屬瓶蓋,金屬餐具', '清洗乾淨後投入金屬類回收桶，體積較大者視當地資源回收處理。', '含危險物或油污的金屬（如油桶）需依特殊回收或一般廢棄物處理。', 'zh-TW'),
        ('glass', '玻璃瓶,玻璃容器,酒瓶,醬油瓶', '清洗乾淨並投入玻璃類回收桶，破損玻璃請以報紙包好再丟棄。', '燒杯、鏡子、玻璃燈罩等特殊玻璃因成分不同可能無法回收，請查當地規定。', 'zh-TW'),
        ('textile', '衣物,被單,毛巾,布料,鞋子(可回收)', '若仍可使用請捐贈或放入指定回收箱；無法使用者請依大型廢棄物或燃燒類規定處理。', '有污漬或潮濕易發霉的衣物先清理再決定回收或丟棄。', 'zh-TW'),
        ('ewaste', '電池,手機,電腦,家電,充電器,電視,冰箱', '小型電池請投入回收箱或專門電池回收桶；電器請送至家電回收點或依大型廢棄物程序處理。', '含汞、鋰電池等屬有害回收範疇，切勿與一般垃圾混放。', 'zh-TW'),
        ('hazard', '電池(鋰電,鹼性),節能燈管,溶劑,油漆,藥品(過期),化學品', '請送到指定的有害廢棄物回收站或由特定回收活動回收，勿直接丟入一般垃圾。', '電池若可能短路請先以膠帶貼住極端；藥品請至藥局或衛生單位回收。', 'zh-TW'),
        ('bulky', '家具,床墊,大型家電,沙發', '依當地大型廢棄物回收規定預約清運或送至指定回收處理中心，並繳交必要費用（若有）。', '可考慮回收再利用或捐贈可用物品以減少資源浪費。', 'zh-TW'),
        ('other', '食用油,廚房油脂', '待油液冷卻後以密封容器回收或送至資源回收點，避免倒入水槽造成下水道阻塞。', '少量油可以紙巾吸乾後以一般垃圾處理，但大量廚房油應回收再利用。', 'zh-TW'),
        ('other', '保麗龍,發泡材料,泡綿', '若乾淨且分隔單一材質，部分回收站可回收；否則以一般垃圾或依當地規定回收。', '帶有食物殘渣或油污的保麗龍不可回收。', 'zh-TW'),
        ('other', '不可回收,混合垃圾,髒污物,衛生紙,紙尿褲,棉花棒', '請以一般垃圾袋妥善包裝後丟棄，特殊臭味或滲漏請密封處理。', '衛生紙、紙尿褲與被嚴重污染的紙類屬一般垃圾。', 'zh-TW'),
        ('hazard', '針頭,醫療廢棄物,血液污染物', '請按醫療廢棄物規定處理，針頭需放入硬殼容器並交由醫療機構或合約廢棄物處理業者處理。', '切勿直接丟入一般垃圾以免造成他人傷害或感染風險。', 'zh-TW'),
        ('other', '餅乾袋,真空包裝,多層複合包材', '多層複合材質通常無法回收，請以一般垃圾處理或依當地指定回收方式。', '如能分離成單一材質則依材質分類回收。', 'zh-TW'),
        ('metal', '電線,銅線,金屬零件,螺絲', '清理後送至金屬回收或資源回收站，電子線材若含塑膠外皮請先分離（若可）。', '有價值金屬可尋求專業回收以提高再利用率。', 'zh-TW'),
        ('other', '可用傢俱,可用電器,書籍(完整)', '若狀態良好，建議捐贈或上傳二手平台，或交由社區資源回收中心接受。', '捐贈前請清潔並確認無重大損壞。', 'zh-TW'),
        ('bulky', '自行車,腳踏車', '可聯絡當地清潔隊預約收運時間，或交由自行車行回收。', '若外觀良好且功能正常，建議優先捐贈或至二手市場交流。', 'zh-TW'),
        ('food', '廚餘', '請投入廚餘回收桶。', '盡量瀝乾水分，並去除包裝。', 'zh-TW'),
        ('paper', '紙類', '請投入紙類回收。', '保持乾燥，去除膠帶等雜質。', 'zh-TW'),
        ('plastic', '塑膠類', '請投入塑膠回收。', '請先沖洗乾淨。', 'zh-TW'),
        ('metal', '金屬類', '請投入金屬回收。', '請先沖洗乾淨。', 'zh-TW'),
        ('glass', '玻璃類', '請投入玻璃回收。', '請先沖洗乾淨。', 'zh-TW'),
        ('textile', '紡織品', '請投入舊衣回收箱。', '乾淨衣物可回收，破損或髒污則為一般垃圾。', 'zh-TW'),
        ('ewaste', '電子廢棄物', '請交給資源回收車或指定回收點。', '回收前請移除電池並清除個資。', 'zh-TW'),
        ('hazard', '有害垃圾', '需交由專門回收管道處理。', '切勿混入一般垃圾或資源回收。', 'zh-TW'),
        ('bulky', '大型廢棄物', '需聯絡當地清潔隊預約清運。', '請勿隨意棄置。', 'zh-TW'),
        ('other', '其他/一般垃圾', '請丟入一般垃圾桶。', '無法回收的物品皆屬此類。', 'zh-TW'),
        
        # === English rules (en) ===
        ('food', 'Food Waste,Leftovers,Fruit Peels,Vegetable Scraps,Tea Leaves,Coffee Grounds', 'Put into the designated food waste bin or compost collection. Drain excess liquid and remove plastic packaging before disposal.', 'Do not mix with plastics, metals, glass or disposable tableware. Bones may be treated as general waste depending on local rules.', 'en'),
        ('food', 'Food Waste Bag,Compost Bin', 'Use a biodegradable or local-authority-approved food waste bag; seal before disposing into the designated collection.', 'If no food waste collection is available, dispose as regular trash and avoid leakage.', 'en'),
        ('paper', 'Tetra Pak,Beverage Carton,Milk Carton,Soya Milk Carton', 'Empty and rinse, flatten, then put into the paper-container recycling bin.', 'Remove straws and plastic films; straws/films should be recycled as plastic if separable.', 'en'),
        ('paper', 'Newspaper,Books,Office Paper,Envelopes,Brochures,Cardboard', 'Flatten and bundle; remove tape and staples before putting into the paper recycling bin.', 'Do not include heavily soiled or grease-stained paper.', 'en'),
        ('plastic', 'Plastic Bottles,Plastic Containers,Plastic Packaging(Clean)', 'Rinse clean and, when appropriate, flatten bottles. Remove lids if required by local guidelines and place in plastic recycling.', 'Composite snack/food bags are usually not recyclable. Check local rules for film/plastic bag collection.', 'en'),
        ('other', 'Plastic Bags,Film Packaging,Cling Film', 'Clean and dry single-material plastic bags may be recycled at designated drop-off points; dirty or multi-layer packaging should be disposed as general waste.', 'Do not mix plastic film with paper recycling to avoid contamination.', 'en'),
        ('metal', 'Metal Cans,Aluminum Cans,Metal Lids,Metal Utensils', 'Rinse and place into the metal recycling bin. Sharp edges should be handled carefully.', 'Large oily containers may need special handling and cannot be recycled through standard streams.', 'en'),
        ('glass', 'Glass Bottles,Glass Jars,Wine Bottles,Sauce Jars', 'Rinse and put into the glass recycling bin. Wrap broken glass in newspaper before disposal.', 'Specialty glass (tempered, mirror glass) may not be accepted in regular glass recycling.', 'en'),
        ('textile', 'Clothes,Bedding,Towels,Shoes', 'Donate usable items or place in textile collection bins. Heavily soiled or wet textiles may need to be disposed as general waste.', 'Repair or upcycle if possible to extend useful life.', 'en'),
        ('ewaste', 'Batteries,Mobile Phones,Computers,Chargers,TVs,Refrigerators', 'Take small batteries to battery recycling bins; bring electronics to designated e-waste drop-off or collection events for safe recycling.', 'Lithium batteries and items containing hazardous substances must not be placed in general trash.', 'en'),
        ('hazard', 'Batteries(Alkaline,Lithium),Fluorescent Tubes,Paints,Solvents,Expired Medicine,Chemicals', 'Deliver to hazardous waste collection centers or scheduled hazardous waste events; do not throw into regular bins.', 'Tape battery terminals to prevent short-circuiting; consult local guidelines for pharmaceutical disposal.', 'en'),
        ('bulky', 'Furniture,Mattresses,Large Appliances,Sofa', 'Arrange pickup or drop-off according to local bulky waste procedures, which may include scheduling and fees.', 'Consider donation or reuse programs for items in good condition.', 'en'),
        ('other', 'Cooking Oil,Used Cooking Oil', 'Allow to cool and collect in a sealed container; bring to used oil recycling points. Do not pour down the drain.', 'Small amounts may be absorbed with paper and disposed as general waste if local regulations permit.', 'en'),
        ('other', 'Polystyrene,Styrofoam,Expanded Polystyrene', 'If clean and accepted locally, bring to specific recycling points; otherwise dispose as general waste.', 'Food-contaminated foam cannot be recycled.', 'en'),
        ('other', 'Non-Recyclable,Contaminated Waste,Soiled Paper,Tissue,Diapers,Cotton Swabs', 'Place in the regular trash. Seal if smelly or moist to prevent leakage.', 'Used tissues, diapers and heavily contaminated paper should be treated as general waste.', 'en'),
        ('hazard', 'Needles,Syringes,Medical Waste,Blood-Contaminated Materials', 'Follow medical waste disposal rules: place sharps in rigid containers and return to medical facilities or authorized handlers.', 'Do not dispose sharps in household trash to avoid risk of injury and infection.', 'en'),
        ('other', 'Composite Packaging,Snack Packs,Multi-layer Foil Bags', 'Composite and multi-layer packaging is generally not recyclable; dispose as regular waste unless local separation is possible.', 'If materials can be separated into single materials, recycle accordingly.', 'en'),
        ('metal', 'Wires,Copper Wiring,Small Metal Parts,Screws', 'Deliver to metal recycling facilities or resource recovery centers.', 'Remove non-metal parts where feasible to improve recyclability.', 'en'),
        ('other', 'Usable Furniture,Working Appliances,Intact Books', 'Donate or reuse via second-hand channels or community collection services.', 'Clean items and check acceptance rules before donation.', 'en'),
        ('bulky', 'Bicycle,Bike', 'Contact your local sanitation department for a scheduled pickup, or take it to a bike shop for recycling.', 'If in good condition, consider donating or selling it first.', 'en'),
        ('food', 'Food Waste', 'Put into the compost bin.', 'Please drain excess liquid and remove packaging.', 'en'),
        ('paper', 'Paper', 'Put into paper recycling.', 'Keep it dry and remove any non-paper items like tape.', 'en'),
        ('plastic', 'Plastic', 'Put into plastic recycling.', 'Please rinse it first.', 'en'),
        ('metal', 'Metal', 'Put into metal recycling.', 'Please rinse it first.', 'en'),
        ('glass', 'Glass', 'Put into glass recycling.', 'Please rinse it first.', 'en'),
        ('textile', 'Textile', 'Put into a clothing donation bin.', 'Clean clothes are recyclable; damaged or soiled ones are general waste.', 'en'),
        ('ewaste', 'E-Waste', 'Take to a designated collection point or recycling vehicle.', 'Remove batteries and erase personal data before recycling.', 'en'),
        ('hazard', 'Hazardous Waste', 'Must be handled by a specialized recycling service.', 'Do not mix with general or recyclable waste.', 'en'),
        ('bulky', 'Bulky Waste', 'Requires a scheduled pickup from your local sanitation department.', 'Do not leave it on the street.', 'en'),
        ('other', 'Other/General Waste', 'Put into the regular trash can.', 'Items that cannot be recycled belong here.', 'en'),
    ]

    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_name_lang ON waste_info (name, language)")
        cursor.execute("DELETE FROM waste_info")
        logger.info("Cleared all old default data.")
        cursor.executemany('INSERT INTO waste_info (category, name, disposal_method, tips, language) VALUES (?, ?, ?, ?, ?)', default_waste_info)
        conn.commit()
        logger.info(f"Inserted or updated {cursor.rowcount} new expert rules.")
    except Exception as e:
        logger.error(f"Error inserting default data: {e}")
        raise

if __name__ == "__main__":
    init_database()
    print("Database initialized successfully with the latest user-provided expert rules!")

