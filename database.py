# 檔案: database.py
# (此版本已修正 UNIQUE constraint 錯誤)

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
            
            # 1. 使用者 (不變)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, language TEXT, created_at TIMESTAMP,
                    last_active TIMESTAMP, eco_points INTEGER)
            ''')
            # 2. 分類紀錄 (不變)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS classifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, category TEXT, confidence REAL,
                    image_path TEXT, is_correct BOOLEAN, feedback TEXT, created_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id))
            ''')
            
            # (舊的 waste_info 資料表，如果存在則刪除，以便移轉)
            cursor.execute("DROP TABLE IF EXISTS waste_info")

            # 3. 專家規則資料表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS waste_info_expert (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, name_keywords TEXT, 
                    disposal_method TEXT, tips TEXT, language TEXT)
            ''')
            
            # --- vvv 修正處 vvv ---
            # 4. 通用規則資料表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS waste_info_general (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    category TEXT, 
                    name TEXT, 
                    disposal_method TEXT, 
                    tips TEXT, 
                    language TEXT,
                    UNIQUE(category, language) 
                )
            ''')
            # --- ^^^ 修正處 ^^^ ---

            conn.commit()
            logger.info("Database tables created or already exist (expert/general separated).")
            
            # 插入或更新您提供的最新資料
            insert_default_data(conn)
            
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def insert_default_data(conn):
    """(最新版) 將規則分別插入 expert 和 general 資料表"""
    cursor = conn.cursor()
    
    # --- 1. 專家規則列表 (Expert Rules) ---
    default_expert_rules = [
        # === 繁體中文規則 (zh-TW) ===
        # --- 紙類 (Paper) ---
        ('paper', '雜誌,影印紙,包裝紙,紙製茶葉罐,便條紙,日曆,紙袋,再生紙,報紙,電腦報表紙,宣傳單,衛生紙滾筒,電話簿,月曆,紙箱,瓦楞紙,書籍,購物紙袋,信封,名片,筆記本,水果套袋', '請先行除去塑膠封面、膠帶、線圈、釘書針等非紙類物品後，攤平打包集中回收。', '水果套袋請先除去綁繩、樹枝、膠帶等。', 'zh-TW'),
        ('paper', '紙容器,鋁箔包,新鮮屋,利樂皇,紙餐具,紙杯,紙碗,紙餐盤,紙餐盒', '內容物倒空，稍微擦拭或沖洗，壓扁後回收。', '紙盒包或鋁箔包要先將吸管去除再壓扁。', 'zh-TW'),
        ('other', '紙尿褲,紙尿片,衛生紙,衛生棉,複寫紙,蠟紙,離型紙,貼紙底襯,轉印紙,感熱紙,電子發票,砂紙,塑膠光面紙,髒污的紙張,炮竹類紙屑', '這些皆為不可回收的複合材質或髒污紙張，請打包後交給垃圾車。', '感熱紙(如電子發票)含有化學物質，不可回收。', 'zh-TW'),
        # --- 金屬類 (Metal) ---
        ('metal', '鐵容器,鐵罐,鐵窗,鐵板,鐵棍,鐵籠,鐵箱,鐵欄杆,鐵製鉛筆盒,鐵門,鐵架,鐵棒,鐵鉤,鐵桶,鐵條,鐵鐘,鐵器,鐵鍋,鐵櫃,鐵絲,圖釘,鐵釘,鐵碗,鐵塊,鐵鍊,鐵皮,鐵杯,鐵盆,鐵鎚頭,菜刀刀身,雨傘骨架,鐵製餅乾盒,鋼筋', '請先倒空內容物，用水略為沖洗後回收。', '雨傘布、坐墊等複合材質需拆除，只回收骨架。', 'zh-TW'),
        ('metal', '鋁容器,鋁罐,鋁鍋,鋁盆,鋁門窗外框,鋁合金鋼圈', '請先倒空內容物，用水略為沖洗，壓扁後回收。', '保持乾燥與潔淨。', 'zh-TW'),
        ('metal', '包覆銅線電線,不銹鋼製品,金屬釘書機,金屬製菜籃,金屬剪刀,金屬湯匙,叉子,鑰匙,門鎖,金屬製衣架,銅製品,不銹鋼瓦斯爐,鋼圈', '直接交付資源回收車即可。', '電線外層的塑膠皮不需特別剝除。', 'zh-TW'),
        ('hazard', '氣體鋼瓶,滅火器,瓦斯鋼瓶', '應交由原販賣業者逆向回收，或洽詢瓦斯行、檢驗場處理。', '這些是壓力容器，切勿自行處理或直接交給清潔隊，以免發生危險。', 'zh-TW'),
        ('other', '保險絲,電話線,網路線', '此類物品目前無法有效回收，請以一般垃圾處理。', '雖然內含金屬，但因雜質過多、處理成本高，不在回收範圍內。', 'zh-TW'),
        # --- 塑膠類 (Plastic) ---
        ('plastic', '塑膠容器,PET瓶,PVC瓶,PP杯,PE瓶,PS瓶,養樂多瓶,塑膠盒,塑膠盆,塑膠桌椅,光碟片,塑膠製資料夾,保鮮盒,塑膠臉盆,塑膠花盆,壓克力,包裝封膜,塑膠管,膠水瓶,塑膠菜籃,塑膠製衣架,塑膠水桶,安全帽,錄影帶,錄音帶,塑膠玩具,塑膠類免洗餐具,保麗龍餐具,生鮮托盤', '請先倒空內容物，用水略為沖洗後回收。', '乾淨的保麗龍餐具或生鮮托盤是可以回收的。', 'zh-TW'),
        ('plastic', '乾淨的塑膠袋', '請將袋內垃圾倒乾淨，打結後集中成一包交付回收。', '只回收乾淨的、單純的塑膠袋。', 'zh-TW'),
        ('plastic', '乾淨的包裝用保麗龍,漁貨箱,冰品盒,蛋糕盒,電子電器包裝材', '請先去除內容物、膠帶、木材、鐵釘等，並沖洗乾淨。', '建築工程用的施工保麗龍不可回收。', 'zh-TW'),
        ('other', '塑膠膜,化學纖維物品,塑膠布,樹脂,安全座椅,護貝膠膜,腳踏墊,保鮮膜,墊子,泡棉,旅行袋,膠帶,雨衣,原子筆,吸管,飼料袋,唱片,刷子,底片,板擦,塑膠鉛筆盒,筷子,牙籤,牙線,橡膠製品', '這些皆為不可回收的複合材質或體積過小物品，請以一般垃圾處理。', '廢輪胎除外，需另外回收。', 'zh-TW'),
        ('other', '髒污的塑膠袋,內層有錫箔或鋁箔的塑膠袋,茶包,餅乾袋', '此類複合材質或髒污的塑膠袋無法回收，請以一般垃圾處理。', '判斷標準是袋子內層是否為銀色或有其他材質。', 'zh-TW'),
        # --- 玻璃類 (Glass) ---
        ('glass', '香水,香水瓶', '需將「內容物」與「空瓶」分開處理。 1. 內容物處理：將香水液體用廢布或紙巾吸收，待揮發後丟入「一般垃圾」。 2. 空瓶回收：將清洗乾淨的空瓶依照瓶身材質（多為玻璃）進行回收。', '重點：切勿將香水液體直接倒入水槽或馬桶！若為噴霧罐，請在戶外通風處將內容物完全排空，再依「金屬類」回收。', 'zh-TW'),
        ('glass', '玻璃容器,玻璃瓶,酒瓶,玻璃盤,玻璃杯,玻璃碗,玻璃燭臺,門窗玻璃,魚缸', '去除瓶蓋、吸管，倒空內容物並略為沖洗後回收。', '破損玻璃請用紙箱或報紙包好，並註明「碎玻璃」，保護清潔人員。', 'zh-TW'),
        ('other', '隔熱玻璃,汽車擋風玻璃,防火玻璃,玻璃墊,燈具,鏡子', '因材質成分不同，不可與一般玻璃混合回收，請以一般垃圾處理或洽詢清潔隊。', '這些是強化或特殊處理過的玻璃。', 'zh-TW'),
        # --- 紡織品 (Textile) ---
        ('textile', '舊衣,上衣,褲子,裙子,洋裝,外套,西裝', '以可穿著為主，清洗乾淨後打包成袋，交給回收車或舊衣回收箱。', '貼身衣物因衛生考量不回收。衣物需乾淨無破損、黃斑或異味。', 'zh-TW'),
        ('other', '枕頭,棉被,床單,地毯,襪子,鞋類,皮衣,貼身衣物,絨毛玩具,窗簾,毛線,皮帶,包包,帽子,抹布', '這些物品因衛生、材質或破損等因素無法回收，請以一般垃圾處理。', '外觀良好且功能未喪失的鞋子、包包、絨毛玩具可考慮至二手市場交流。', 'zh-TW'),
        # --- 電子廢棄物 (E-waste) ---
        ('ewaste', '大型家電,電視機,電冰箱,洗衣機,冷暖氣機,影印機,音響,抽油煙機', '可交由經銷商逆向回收，或電洽清潔隊約定收運時間。', '回收前請盡量清空內部物品。', 'zh-TW'),
        ('ewaste', '小型家電,行動電話,電熱水瓶,電磁爐,脫水機,電鍋,飲水機,微波爐,烘乾機,吹風機,烤箱,電風扇,電暖爐,烘碗機,咖啡機,收錄音機,傳真機,影音光碟機,錄放影機,充電器', '直接交付資源回收車即可。', '回收前請移除電池並清除個資。', 'zh-TW'),
        ('ewaste', '資訊物品,筆記型電腦,監視器,螢幕,主機板,硬式磁碟機,電源供應器,機殼,印表機,不斷電系統主機,鍵盤,平板電腦,外接硬碟,行動電源', '可交給資源回收車或送至資訊商品販賣業者逆向回收。', '電腦零件、滑鼠、滑鼠墊等周邊不可回收。另外，部分有價值的電子廢棄物如:二手筆電、顯示器、手機等，可以透過二手交易平台販賣，或交由合法回收處理業者', 'zh-TW'),
        ('ewaste', '光碟片,CD,VCD,DVD', '請收集後裝成一袋交付回收。', '不含外殼，外殼若為塑膠材質可另行回收。', 'zh-TW'),
        # --- 有害垃圾 (Hazardous) ---
        ('hazard', '廢電池,水銀電池,鹼性電池,鋰電池,鎳鎘電池,充電電池,鈕扣型電池,鉛蓄電池', '交給資源回收車，或連鎖超商、量販店等販賣業者逆向回收。', '車用鉛蓄電池可交由汽_機車行或保修廠回收。', 'zh-TW'),
        ('hazard', '照明光源,日光燈,環管日光燈,燈泡,冷陰極燈', '可先用紙套裝好，不要打破，交給資源回收車或照明光源販賣業者回收。', '燈帽直徑2.6公分以下的傳統燈泡不可回收。', 'zh-TW'),
        ('hazard', '水銀體溫計', '請使用原包裝盒打包好，特別交付給資源回收車隨車人員。', '不包含實驗室用的溫度計。', 'zh-TW'),
        ('hazard', '廢農藥容器', '請至少清洗三次，並將清洗液重複噴灑利用，清除內容物後打包回收。', '可送交農會設置的回收點或資源回收車。', 'zh-TW'),
        ('hazard', '油漆,油漆溶劑,水泥漆,凡立水', '內容物若未使用完，應將蓋子蓋緊，交由資源回收車或洽詢清潔隊。不可倒入水槽。', '容器若已清空，則可依其材質（金屬、塑膠）進行回收。', 'zh-TW'),
        # --- 大型廢棄物 (Bulky) ---
        ('bulky', '廢機動車輛,汽車,機車', '廢機動車輛（汽車與機車）應洽詢合法的廢車回收商進行報廢與回收處理。完成合法報廢後，民眾可獲得少額回收獎勵金；若同時報廢老舊汽車或機車並購買電動車，還可能申請高額的汰舊換新補助。', '報廢前，民眾須先至監理站辦理車輛報廢登記。', 'zh-TW'),
        ('bulky', '堪用家具,彈簧床墊', '可與清潔隊各區隊約定收運時間到府回收。', '這是針對大型垃圾的專門服務。', 'zh-TW'),
        ('bulky', '自行車,腳踏車', '可與清潔隊約定收運時間，或交由自行車行回收。', '回收時可能需要交付切結書。', 'zh-TW'),
        ('bulky', '廢輪胎', '可由輪胎行、汽機車行、保修廠逆向回收或交由資源回收車回收。', '不包含特種車輛實心輪胎或飛機胎。', 'zh-TW'),
        ('bulky', '陶瓷,磚瓦,廢棄陶器,瓷器,碗盤,花瓶,磁磚,馬桶,洗手台,磚頭,屋瓦', '少量請直接交付資源回收車，大量請與清潔隊約定時間。', '請先分類裝袋。', 'zh-TW'),
        # --- 廚餘 (Food Waste) ---
        ('food', '生熟廚餘,剩菜,剩飯,菜根,果皮,魚骨,肉骨,雞肉,炸雞,豬肉,牛肉,食物', '瀝除水分後，倒入廚餘回收桶。', '硬質的果核(芒果、桃、李)、貝殼、竹筍殼、甘蔗皮等應作為堆肥廚餘或一般垃圾。', 'zh-TW'),
        # --- 其他 (Other) ---
        ('other', '潤滑油', '應交由機車行、汽車維修廠及加油站等設置的廢潤滑油回收站進行回收。', '不可倒入水槽或與其他回收物混合。', 'zh-TW'),
        ('other', '食用油,回鍋油,過期食用油', '請先以塑膠容器盛裝後，交由資源回收車回收。', '切勿倒入排水管，會造成嚴重堵塞。', 'zh-TW'),
        ('other', '暖暖包', '不含塑膠外包裝，可交付資源回收車回收。', '這屬於其他回收項目。', 'zh-TW'),
        # --- 動物屍體 (Animal) ---
        ('animal', '動物屍體,寵物,寵物屍體,寵物遺體,流浪動物,流浪狗,流浪貓,街頭動物屍體,路倒動物,野生禽鳥,鳥屍體,死掉的鳥,貓,狗,鳥,屍體,遺體', '1. 自家寵物死亡：\n委託動物醫院、寵物業者協助處理（火化），或依《廢棄物清理法》自行包裝後交給清潔隊。\n\n2. 街頭流浪動物死亡：\n撥打1999通報專線或聯繫當地環保局/動保處。\n\n3. 野生禽鳥屍體：\n應立即撥打當地政府專線通報（如1999）。', '• 注意!機器人無法判斷生物是否有生命跡象，請尋求專業人士判斷!\n• 若交給清潔隊，請務必妥善密封包裝。\n• 處理流浪/野生動物，請勿徒手接觸。', 'zh-TW'),

        # === English Rules (en) ===
        # ... (所有英文專家規則保持不變) ...
        ('paper', 'Magazines, copy paper, wrapping paper, paper tea canisters, memo pads, calendars, paper bags, recycled paper, newspapers, computer paper, flyers, toilet paper rolls, phone books, wall calendars, cardboard boxes, corrugated paper, books, shopping bags, envelopes, business cards, notebooks, fruit protection bags', 'Please remove non-paper items like plastic covers, tape, coils, and staples first. Flatten and bundle for recycling.', 'For fruit protection bags, please remove strings, branches, and tape first.', 'en'),
        ('paper', 'Paper containers, Tetra Paks, Fresh House cartons, paper tableware, paper cups, paper bowls, paper plates, paper boxes', 'Empty the contents, wipe or rinse briefly, then flatten for recycling.', 'For cartons or Tetra Paks, remove the straw before flattening.', 'en'),
        ('other', 'Diapers, used tissues, sanitary pads, carbon paper, wax paper, release paper (sticker backing), transfer paper, thermal paper (e-receipts), sandpaper, glossy plastic-coated paper, soiled paper, firecracker scraps', 'These are all non-recyclable composite materials or soiled paper. Please bag them and hand them to the garbage truck.', 'Thermal paper (like e-receipts) contains chemicals and is not recyclable.', 'en'),
        ('metal', 'Iron containers, cans, window frames, plates, rods, cages, boxes, railings, pencil cases, doors, shelves, hooks, buckets, bars, bells, cookware, cabinets, wires, thumbtacks, nails, bowls, blocks, chains, sheets, cups, basins, hammerheads, knife blades, umbrella frames, cookie tins, rebar', 'Please empty the contents and rinse lightly before recycling.', 'Composite materials like umbrella fabric and cushions must be removed; only recycle the frame.', 'en'),
        ('metal', 'Aluminum containers, cans, pots, basins, window frames, alloy wheels', 'Empty the contents, rinse lightly, and flatten for recycling.', 'Keep them dry and clean.', 'en'),
        ('metal', 'Copper-clad wires, stainless steel products, metal staplers, metal vegetable baskets, metal scissors, metal spoons, forks, keys, door locks, metal hangers, copper products, stainless steel gas stoves, steel rims', 'Hand them directly to the recycling truck.', 'The outer plastic sheath of wires does not need to be stripped.', 'en'),
        ('hazard', 'Gas cylinders, fire extinguishers, propane tanks', 'Should be returned to the original vendor or taken to a gas company/inspection site for handling.', 'These are pressurized containers. Do not handle them yourself or give them to the cleaning crew to avoid danger.', 'en'),
        ('other', 'Fuses, telephone lines, network cables', 'These items cannot be effectively recycled at present. Please dispose of them as general waste.', 'Although they contain metal, they are not recycled due to excessive impurities and high processing costs.', 'en'),
        ('plastic', 'Plastic containers, PET bottles, PVC bottles, PP cups, PE bottles, PS bottles, Yakult bottles, plastic boxes, basins, tables, chairs, CDs/DVDs, plastic folders, food storage containers, face wash basins, flower pots, acrylics, packaging film, plastic pipes, glue bottles, plastic baskets, plastic hangers, water buckets, helmets, videotapes, cassette tapes, plastic toys, disposable plastic tableware, styrofoam tableware, fresh food trays', 'Please empty the contents and rinse lightly before recycling.', 'Clean styrofoam tableware or fresh food trays are recyclable.', 'en'),
        ('plastic', 'Clean plastic bags', 'Empty any trash from the bag, tie it, and collect them in one bag for recycling.', 'Only clean, single-material plastic bags are recycled.', 'en'),
        ('plastic', 'Clean packaging styrofoam, fish boxes, ice cream boxes, cake boxes, electronic appliance packaging materials', 'Please remove contents, tape, wood, nails, etc., and rinse clean first.', 'Styrofoam used in construction is not recyclable.', 'en'),
        ('other', 'Plastic film, chemical fiber items, plastic sheets, resin, car seats, lamination film, floor mats, cling wrap, cushions, foam, travel bags, tape, raincoats, ballpoint pens, straws, feed bags, records, brushes, camera film, whiteboard erasers, plastic pencil cases, chopsticks, toothpicks, dental floss, rubber products', 'These are all non-recyclable composite or small-sized items. Please dispose of them as general waste.', 'Excluding scrap tires, which should be recycled separately.', 'en'),
        ('other', 'Dirty plastic bags, plastic bags with an inner foil layer, tea bags, snack bags', 'These types of composite or dirty plastic bags are not recyclable. Please dispose of them as general waste.', 'The criteria is whether the inner layer of the bag is silver or made of another material.', 'en'),
        ('glass', 'Perfume, Perfume Bottle', 'The "contents" and "empty bottle" must be handled separately. 1. Contents Disposal: Absorb the liquid with a cloth or paper towel. After it evaporates, throw the absorbent material into "General Waste". 2. Bottle Recycling: Recycle the clean, empty bottle based on its material (usually glass).', 'IMPORTANT: Do not pour liquid perfume down the sink or toilet. For aerosol cans, ensure they are completely empty in a ventilated area before recycling as "Metal".', 'en'),
        ('glass', 'Glass containers, glass bottles, wine bottles, glass plates, glass cups, glass bowls, glass candlesticks, window glass, fish tanks', 'Remove lids and straws, empty the contents, and rinse lightly before recycling.', 'Please wrap broken glass in a cardboard box or newspaper and label it as "broken glass" to protect cleaning personnel.', 'en'),
        ('other', 'Insulated glass, car windshields, fireproof glass, glass mats, lighting fixtures, mirrors', 'Due to different material compositions, these cannot be recycled with regular glass. Please dispose of them as general waste or consult the cleaning crew.', 'These are tempered or specially treated glass.', 'en'),
        ('textile', 'Old clothes, tops, pants, skirts, dresses, jackets, suits', 'Items must be wearable. Please wash them, bag them, and hand them to a recycling truck or place in a clothing donation bin.', 'Undergarments are not recycled for hygiene reasons. Clothes must be clean, undamaged, and free of stains or odors.', 'en'),
        ('other', 'Pillows, quilts, bed sheets, carpets, socks, shoes, leather clothes, underwear, stuffed animals, curtains, yarn, belts, bags, hats, rags', 'These items are not recyclable due to hygiene, material, or damage. Please dispose of them as general waste.', 'Shoes, bags, and stuffed animals in good, functional condition can be exchanged at flea markets.', 'en'),
        ('ewaste', 'Large home appliances, TVs, refrigerators, washing machines, air conditioners, photocopiers, stereos, range hoods', 'Can be returned to the retailer for reverse recycling or call your local cleaning crew to schedule a pickup.', 'Please empty the items as much as possible before recycling.', 'en'),
        ('ewaste', 'Small home appliances, mobile phones, electric kettles, induction cookers, spin dryers, rice cookers, water dispensers, microwaves, dryers, hair dryers, ovens, electric fans, heaters, dish dryers, coffee makers, cassette players, fax machines, VCD/DVD players, VCRs, chargers', 'Hand them directly to the recycling truck.', 'Please remove batteries and erase personal data before recycling.', 'en'),
        ('ewaste', 'IT equipment, laptops, monitors, screens, motherboards, hard drives, power supplies, computer cases, printers, UPS systems, keyboards, tablets, external hard drives, power banks', 'Can be handed to a recycling truck or returned to an IT product retailer for reverse recycling.', 'Peripherals like computer parts, mice, and mouse pads are not recyclable.', 'en'),
        ('ewaste', 'CDs, VCDs, DVDs', 'Please collect them in a bag before handing them over for recycling.', 'This does not include the case; plastic cases can be recycled separately.', 'en'),
        ('hazard', 'Paint, Paint Thinner, Varnish', 'If there is leftover content, seal the can tightly and hand it to a recycling truck or contact the cleaning crew. Do not pour down the drain.', 'If the container is empty, it can be recycled based on its material (metal, plastic).', 'en'),
        ('hazard', 'Used batteries, mercury batteries, alkaline batteries, lithium batteries, nickel-cadmium batteries, rechargeable batteries, button cell batteries, lead-acid batteries', 'Hand over to a recycling truck or return to retailers like convenience stores or hypermarkets for reverse recycling.', 'Lead-acid batteries from vehicles can be returned to scooter/car repair shops.', 'en'),
        ('hazard', 'Lighting sources, fluorescent tubes, circular fluorescent tubes, light bulbs, cold cathode lamps', 'Please pack them in a paper sleeve, do not break them, and hand them to a recycling truck or a lighting retailer for recycling.', 'Traditional light bulbs with a cap diameter under 2.6 cm are not recyclable.', 'en'),
        ('hazard', 'Mercury thermometers', 'Please pack it in its original case and hand it specifically to the personnel on the recycling truck.', 'Does not include laboratory thermometers.', 'en'),
        ('hazard', 'Used pesticide containers', 'Please rinse at least three times, reuse the rinsing liquid for spraying, empty the contents, and then bag for recycling.', 'Can be taken to collection points at local farmers\' associations or given to a recycling truck.', 'en'),
        ('bulky', 'Scrap motor vehicles, cars, motorcycles', 'End-of-life vehicles (including cars and motorcycles) should be properly disposed of through certified vehicle recycling companies. After completing the official scrapping process, owners may receive a small recycling reward. In addition, those who scrap old vehicles and purchase electric ones may be eligible for higher replacement subsidies.', 'Before recycling, the vehicle owner must first complete the deregistration process at the Motor Vehicles Office.', 'en'),
        ('bulky', 'Usable furniture, spring mattresses', 'You can schedule a door-to-door pickup with your local cleaning crew.', 'This is a dedicated service for large waste items.', 'en'),
        ('bulky', 'Bicycles', 'You can schedule a pickup with the cleaning crew or take it to a bicycle shop for recycling.', 'A signed affidavit may be required for recycling.', 'en'),
        ('bulky', 'Scrap tires', 'Can be returned to tire shops, vehicle repair shops for reverse recycling, or handed to a recycling truck.', 'Does not include solid tires for special vehicles or aircraft tires.', 'en'),
        ('bulky', 'Ceramics, bricks, tiles, discarded pottery, porcelain, bowls, plates, vases, toilets, sinks, roof tiles', 'Hand small quantities directly to the recycling truck; for large quantities, please schedule a pickup with the cleaning crew.', 'Please sort and bag them first.', 'en'),
        ('food', 'Raw and cooked food scraps, leftovers, vegetable roots, fruit peels, fish bones, meat bones, fallen leaves, chicken, fried chicken, pork, beef, food', 'Drain excess water before putting into the food waste bin.', 'Hard pits (mango, peach), shells, bamboo shoot husks, and sugarcane peels should be treated as compost or general waste.', 'en'),
        ('other', 'Lubricating oil', 'Should be taken to recycling stations at scooter shops, car repair shops, or gas stations.', 'Do not pour down the sink or mix with other recyclables.', 'en'),
        ('other', 'Cooking oil, used cooking oil, expired cooking oil', 'Please collect it in a plastic container first, then hand it to the recycling truck.', 'Never pour it down the drain as it will cause severe blockages.', 'en'),
        ('other', 'Heating packs', 'Excluding the plastic outer packaging, it can be handed to the recycling truck.', 'This belongs to other recyclable items.', 'en'),
        ('animal', 'Animal carcass, pet death, pet body, stray animal, roadkill, wild bird, dead bird, cat, dog, bird, dead body', '1. Own Pet Death:\nContact a veterinarian or pet cremation service, OR package the body securely and hand it to the sanitation crew.\n\n2. Stray Animal Death (Roadkill):\nCall the 1999 hotline or contact your local Environmental/Animal Protection Office.\n\n3. Wild Bird Carcass:\nImmediately call your local government hotline (e.g., 1999).', '• Attention! Robots cannot determine whether an organism is alive. Please seek professional judgment! \n• If handing to sanitation crew, ensure it is securely sealed.\n• Do not touch stray or wild animals with bare hands.', 'en'),
    ]

    # --- 2. 通用規則列表 (General Rules) ---
    default_general_rules = [
        # (category, name, disposal_method, tips, language)
        # --- 繁體中文 (zh-TW) ---
        ('food', '廚餘', '生、熟食物或殘渣，請瀝乾水分後倒入廚餘回收桶。', '硬質的果核、貝殼等不可混入。', 'zh-TW'),
        ('paper', '紙類', '乾淨的紙張、紙箱、紙容器，請去除雜質、壓平後回收。', '髒污或複合材質的紙張(如衛生紙、感熱紙)為一般垃圾。', 'zh-TW'),
        ('plastic', '塑膠類', '塑膠瓶、塑膠容器、乾淨的塑膠袋與保麗龍，請沖洗乾淨後回收。', '髒污或複合材質的塑膠(如餅乾袋)為一般垃圾。', 'zh-TW'),
        ('metal', '金屬類', '鐵罐、鋁罐等金屬容器，請沖洗乾淨後回收。', '壓力容器(如瓦斯罐)需交由專門管道回收。', 'zh-TW'),
        ('glass', '玻璃類', '玻璃瓶、玻璃容器，請沖洗乾淨後回收。', '鏡子、燈具、強化玻璃為一般垃圾。破損玻璃請包好再丟。', 'zh-TW'),
        ('textile', '紡織品', '乾淨且還能穿的舊衣物，可投入舊衣回收箱或交給回收車。', '枕頭、棉被、襪子、鞋子、貼身衣物等為一般垃圾。', 'zh-TW'),
        ('ewaste', '電子廢棄物', '廢棄的家電、資訊用品(電腦、手機)、光碟片等，請交給回收車或指定回收點。', '回收前請移除電池並清除個資。', 'zh-TW'),
        ('hazard', '有害垃圾', '廢電池、廢燈管、溫度計、過期藥品等，需交由專門回收管道處理。', '切勿混入一般垃圾或資源回收，以免造成環境危害。', 'zh-TW'),
        ('bulky', '大型廢棄物', '廢棄家具、床墊、車輛、輪胎等，需聯絡當地清潔隊預約專門清運。', '請勿隨意棄置，以免受罰。', 'zh-TW'),
        ('animal', '動物屍體', '包含寵物、流浪動物或野生禽鳥。請參閱詳細處理方式，切勿隨意丟棄。', '• 注意！機器人無法判斷生物是否有生命體，請尋求專業人士判斷！\n請勿徒手接觸，並聯繫專門單位處理。', 'zh-TW'),
        ('money', '金錢(貨幣)', '1. 現行流通貨幣 (民國89年起)：\n請勿丟棄！此為法定流通資產。\n\n2. 舊版新臺幣 (票面載明「臺灣銀行」)：\n請持至臺灣銀行各地分行，兌換成等值的現行流通券幣。', '• 舊版兌換範圍：所有載明「臺灣銀行」字樣的鈔券（紀念鈔除外），及民國68年以前的伍圓、壹圓硬幣。\n• 嚴重毀損的現行貨幣也可洽詢臺灣銀行鑑定。', 'zh-TW'),
        ('other', '其他/一般垃圾', '無法回收的物品皆屬此類，請打包後丟入垃圾車。', '包含髒污的回收物、複合材質物品等。', 'zh-TW'),

        # --- English (en) ---
        ('food', 'Food Waste', 'Raw or cooked food scraps. Please drain excess liquid before putting into the food waste bin.', 'Do not mix in hard pits or shells.', 'en'),
        ('paper', 'Paper', 'Clean paper, cardboard, and paper containers. Please remove impurities, flatten, and recycle.', 'Soiled or composite paper (like tissues, thermal paper) is general waste.', 'en'),
        ('plastic', 'Plastic', 'Plastic bottles, containers, clean plastic bags, and Styrofoam. Please rinse clean before recycling.', 'Dirty or composite plastics (like snack bags) are general waste.', 'en'),
        ('metal', 'Metal', 'Iron cans, aluminum cans, and other metal containers. Please rinse clean before recycling.', 'Pressurized containers (like gas canisters) require special handling.', 'en'),
        ('glass', 'Glass', 'Glass bottles and containers. Please rinse clean before recycling.', 'Mirrors, light fixtures, and tempered glass are general waste. Wrap broken glass before disposal.', 'en'),
        ('textile', 'Textile', 'Clean, wearable old clothes can be placed in donation bins or given to recycling trucks.', 'Pillows, quilts, socks, shoes, and underwear are general waste.', 'en'),
        ('ewaste', 'E-Waste', 'Discarded appliances, IT equipment (computers, phones), CDs, etc. Please hand to a recycling truck or designated point.', 'Remove batteries and erase personal data before recycling.', 'en'),
        ('hazard', 'Hazardous Waste', 'Used batteries, light bulbs/tubes, thermometers, expired medicine, etc. Must be handled by specialized services.', 'Do not mix with other waste to avoid environmental harm.', 'en'),
        ('bulky', 'Bulky Waste', 'Discarded furniture, mattresses, vehicles, tires, etc. Requires a scheduled pickup from your local sanitation department.', 'Do not dump illegally to avoid fines.', 'en'),
        ('animal', 'Animal Carcass', 'Includes pets, stray animals, or wild birds. Please refer to specific disposal methods and do not discard casually.', '• Attention! Robots cannot determine whether an organism is alive. Please seek professional judgment! \nPlease do not touch with bare hands; contact specialized units.', 'en'),
        ('money', 'Currency', '1. Current Circulating Currency (Central Bank issue, from 2000):\nDO NOT DISCARD! This is legal tender.\n\n2. Old NTD (Notes marked "Bank of Taiwan"):\nTake to any Bank of Taiwan branch to exchange for current currency.', '• Exchange scope: All notes marked "Bank of Taiwan" (except 50th anniv. plastic note) and 5 NTD/1 NTD coins from before 1979.', 'en'),
        ('other', 'Other/General Waste', 'Items that cannot be recycled belong here. Please bag them for the garbage truck.', 'Includes soiled recyclables and composite material items.', 'en'),
    ]

    try:
        # --- 3. 將規則插入對應的資料表 ---
        
        # 建立索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expert_lang ON waste_info_expert (language)")
        
        # --- vvv 修正處 vvv ---
        # (將 UNIQUE 索引移到 CREATE TABLE 語句中，確保新資料庫也能正確建立)
        # cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_general_cat_lang ON waste_info_general (category, language)")
        # --- ^^^ 修正處 ^^^ ---

        # 清空舊資料
        cursor.execute("DELETE FROM waste_info_expert")
        cursor.execute("DELETE FROM waste_info_general")
        logger.info("Cleared all old default data from expert and general tables.")

        # 插入新資料
        cursor.executemany('INSERT INTO waste_info_expert (category, name_keywords, disposal_method, tips, language) VALUES (?, ?, ?, ?, ?)', default_expert_rules)
        logger.info(f"Inserted {cursor.rowcount} expert rules.")
        
        cursor.executemany('INSERT INTO waste_info_general (category, name, disposal_method, tips, language) VALUES (?, ?, ?, ?, ?)', default_general_rules)
        logger.info(f"Inserted {cursor.rowcount} general rules.")

        conn.commit()
        
    except Exception as e:
        logger.error(f"Error inserting default data: {e}")
        # 如果是因為 UNIQUE 限制導致插入失敗，記錄更詳細的錯誤
        if "UNIQUE constraint failed" in str(e):
            logger.error(f"Database schema constraint failed. Did you update the CREATE TABLE statements in init_database? Error: {e}")
        raise

if __name__ == "__main__":
    init_database()
    print("Database initialized successfully with separated expert and general rules!")



