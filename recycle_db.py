# recycle_db.py
import sqlite3
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from config import Config

logger = logging.getLogger(__name__)
DB_PATH = 'database.db'

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class RecycleDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        # 內存快取（可 call reload_rules() 更新）
        self.rules_cache = {'zh-TW': [], 'en': []}
        self.reload_rules()

    def reload_rules(self, language: Optional[str] = None):
        """從 DB 載入 waste_info，並把 name 欄拆成 keywords list，長詞優先排序。"""
        langs = [language] if language else ['zh-TW', 'en']
        with _get_conn() as conn:
            cursor = conn.cursor()
            for lang in langs:
                cursor.execute("SELECT id, category, name, disposal_method, tips FROM waste_info WHERE language = ?", (lang,))
                rows = cursor.fetchall()
                proc = []
                for r in rows:
                    raw = r['name'] or ''
                    # 把逗號、換行等切開成關鍵字；也支援 /regex/ 形式
                    parts = [p.strip() for p in re.split(r'[,\n]+', raw) if p.strip()]
                    keywords = []
                    for p in parts:
                        if p.startswith('/') and p.endswith('/'):
                            # regex token
                            try:
                                keywords.append({'type': 'regex', 'pattern': re.compile(p[1:-1], re.IGNORECASE)})
                            except re.error:
                                # 若 regex 錯誤，降為普通字串
                                keywords.append({'type': 'text', 'text': p})
                        else:
                            keywords.append({'type': 'text', 'text': p})
                    # 長詞優先（文字型關鍵字）
                    keywords_sorted = sorted([k for k in keywords if k['type']=='text'], key=lambda x: len(x['text']), reverse=True)
                    # regex 型關鍵字放後面
                    regex_ks = [k for k in keywords if k['type']=='regex']
                    keywords_sorted.extend(regex_ks)

                    proc.append({
                        'id': r['id'],
                        'category': r['category'],
                        'name': r['name'],
                        'keywords': keywords_sorted,
                        'disposal_method': r['disposal_method'],
                        'tips': r['tips']
                    })
                self.rules_cache[lang] = proc
        logger.info("Rules reloaded into cache.")

    # -------------------------
    # 高階函式：以 item_name 與（選擇性）AI 初步分類及其信心，做最終分類
    # -------------------------
    def classify_text(self, item_name: str, language: str = 'zh-TW', ai_label: Optional[str] = None, ai_confidence: Optional[float] = None) -> Dict:
        """
        核心分類入口：
        - 1) 先做 overrides (硬性規則，regex) 處理（例如汽車、香水、噴霧罐）
        - 2) 在 rules_cache 中做長詞優先、整詞/邊界/substring 的多層比對，計算 confidence
        - 3) 若 AI 提供初步類別 (ai_label) 與信心 (ai_confidence)，會與規則匹配結果合併（權重融合）
        - 回傳：category, category_name, disposal_method, tips, confidence, matched_keyword
        """
        try:
            if not item_name or item_name.strip() == '':
                return {'category': 'other', 'category_name': '其他' if language=='zh-TW' else 'Other', 'disposal_method': '', 'tips': '', 'confidence': 0.0}

            item_raw = item_name.strip()
            item_proc = item_raw.lower() if language == 'en' else item_raw

            # ---------- Overrides: 高優先度正則或字串（避免常見誤判） ----------
            overrides = {
                'zh-TW': [
                    (re.compile(r'汽車|轎車|車輛|卡車|貨車|車子'), 'bulky', '車輛屬大型廢棄物或需報廢，請聯絡清潔隊或車行辦理。'),
                    (re.compile(r'機車|摩托車'), 'bulky', '機車屬特殊回收/報廢項目，請依地方法規處理。'),
                    (re.compile(r'香水|香氛|香水瓶|香氛瓶'), 'hazard', '含揮發性有機溶劑，建議送至有害廢棄物回收。'),
                    (re.compile(r'噴霧罐|氣霧罐'), 'hazard', '增壓容器可能易燃或爆裂，請至有害廢棄物回收站。'),
                    (re.compile(r'汽車電池|車用電池|鉛酸電池'), 'hazard', '含重金屬與酸液，請送指定電池或有害廢棄物處理。'),
                ],
                'en': [
                    (re.compile(r'\bcar\b|\bvehicle\b|\bautomobile\b'), 'bulky', 'Vehicle requires bulky-waste handling — contact local sanitation or recycling center.'),
                    (re.compile(r'\bmotorbike\b|\bmotorcycle\b'), 'bulky', 'Motorcycle requires special handling or decommissioning.'),
                    (re.compile(r'\bperfume\b|\bfragrance\b'), 'hazard', 'Contains volatile organic solvents — treat as hazardous.'),
                    (re.compile(r'\baerosol\b|\bspray can\b'), 'hazard', 'Pressurized container; return to hazardous collection.'),
                ]
            }

            for pat, forced_cat, note in overrides.get(language, []):
                if pat.search(item_proc):
                    # 盡量從通用 category 規則取說明
                    with _get_conn() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT name, disposal_method, tips FROM waste_info WHERE category = ? AND language = ? LIMIT 1", (forced_cat, language))
                        row = cursor.fetchone()
                        if row:
                            return {
                                'category': forced_cat,
                                'category_name': row['name'],
                                'disposal_method': row['disposal_method'] or note,
                                'tips': row['tips'],
                                'confidence': 0.98,
                                'matched_keyword': pat.pattern
                            }
                    return {'category': forced_cat, 'category_name': forced_cat, 'disposal_method': note, 'tips': '', 'confidence': 0.98, 'matched_keyword': pat.pattern}

            # ---------- 權重化比對（rules_cache） ----------
            rules = self.rules_cache.get(language, [])
            best_score = 0.0
            best_rule = None
            best_kw = None

            # tokenization for english
            en_tokens = re.split(r'\W+', item_proc) if language == 'en' else re.split(r'[\s,，]+', item_proc)

            for rule in rules:
                for kw in rule['keywords']:
                    if kw['type'] == 'text':
                        kw_text = kw['text'].lower() if language == 'en' else kw['text']
                        # 精確整串比對（最高分）
                        if kw_text == item_proc:
                            score = 1.0
                        # 英文 whole-word 比對
                        elif language == 'en' and re.search(r'\b' + re.escape(kw_text) + r'\b', item_proc):
                            score = 0.95
                        # 中文包含比對（長詞優先已處理）
                        elif language == 'zh-TW' and kw_text in item_proc:
                            score = 0.95
                        # substring (英文)
                        elif language == 'en' and kw_text in item_proc:
                            score = 0.9
                        # tokens match
                        elif language == 'en' and kw_text in en_tokens:
                            score = 0.85
                        # 部分詞匹配（中文斷詞比對）
                        elif language == 'zh-TW':
                            tokens = re.split(r'[\s,，]+', item_proc)
                            score = 0.0
                            for t in tokens:
                                if t and (t in kw_text or kw_text in t):
                                    score = 0.75
                                    break
                        else:
                            score = 0.0
                    else:  # regex
                        pat = kw['pattern']
                        if pat.search(item_proc):
                            score = 0.95
                        else:
                            score = 0.0

                    if score > best_score:
                        best_score = score
                        best_rule = rule
                        best_kw = kw.get('text') if kw.get('type') == 'text' else f"/{kw['pattern'].pattern}/"

                    # 若高分則可中斷
                    if best_score >= 0.995:
                        break
                if best_score >= 0.995:
                    break

            # ---------- AI label 融合（若有） ----------
            # 若提供 ai_label 且 ai_confidence，將其映射到 Config.WASTE_CATEGORIES（若可能）
            ai_influence = 0.0
            ai_map_category = None
            if ai_label and ai_confidence:
                # 嘗試用 ai_label 做 keyword match（用同樣的 rules 去 match）
                label_proc = ai_label.strip().lower() if language == 'en' else ai_label.strip()
                # 直接比對 rules 中是否有對應 keyword
                for rule in rules:
                    for kw in rule['keywords']:
                        if kw['type']=='text':
                            t = kw['text'].lower() if language=='en' else kw['text']
                            if (language=='en' and t == label_proc) or (language!='en' and t == label_proc):
                                ai_map_category = rule['category']
                                break
                        else:
                            if kw['pattern'].search(label_proc):
                                ai_map_category = rule['category']
                                break
                    if ai_map_category:
                        break
                # 若 ai_map_category 有值，則 ai_influence 為 ai_confidence 的比例（0..0.4）
                if ai_map_category:
                    ai_influence = min(max(ai_confidence, 0.0), 1.0) * 0.4  # 上限 0.4

            # ---------- 結果產出 ----------
            if best_rule:
                base_conf = best_score  # 0..1
                combined_conf = base_conf + ai_influence
                combined_conf = min(combined_conf, 0.99)
                return {
                    'category': best_rule['category'],
                    'category_name': best_kw or (best_rule['name'].split(',')[0] if best_rule['name'] else best_rule['category']),
                    'disposal_method': best_rule['disposal_method'],
                    'tips': best_rule['tips'],
                    'confidence': round(combined_conf, 3),
                    'matched_keyword': best_kw
                }

            # ---------- fallback: 以 general other 回傳 ----------
            # 若沒有任何匹配，回傳 other/general 類別的說明（如果 DB 有）
            with _get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT category, name, disposal_method, tips FROM waste_info WHERE category = ? AND language = ? LIMIT 1", ('other', language))
                row = cursor.fetchone()
                if row:
                    return {
                        'category': row['category'],
                        'category_name': row['name'],
                        'disposal_method': row['disposal_method'],
                        'tips': row['tips'],
                        'confidence': 0.35,
                        'matched_keyword': None
                    }

            return {'category': 'other', 'category_name': '其他' if language=='zh-TW' else 'Other', 'disposal_method': '', 'tips': '', 'confidence': 0.35, 'matched_keyword': None}

        except Exception as e:
            logger.exception(f"Error classify_text: {e}")
            return {'category': 'other', 'category_name': '其他' if language=='zh-TW' else 'Other', 'disposal_method': '', 'tips': '', 'confidence': 0.0, 'matched_keyword': None}

    # ---------- 其他便利函式 ----------
    def get_waste_info(self, category: str, language: str = 'zh-TW') -> Optional[Dict]:
        """取得 category 的一般說明（直接從 DB 讀取）"""
        try:
            with _get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT category, name, disposal_method, tips FROM waste_info WHERE category = ? AND language = ? LIMIT 1", (category, language))
                row = cursor.fetchone()
                if row:
                    return {'category': row['category'], 'category_name': row['name'], 'disposal_method': row['disposal_method'], 'tips': row['tips']}
                return None
        except Exception as e:
            logger.exception(f"Error get_waste_info: {e}")
            return None

    # 使用者資料、紀錄與統計函式（維持與你的 DB schema 相容）
    def get_or_create_user(self, user_id: str, language: str = 'zh-TW') -> Dict:
        try:
            with _get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id, language, created_at, last_active, eco_points FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                if row:
                    cursor.execute('UPDATE users SET last_active = datetime("now","localtime") WHERE user_id = ?', (user_id,))
                    conn.commit()
                    return dict(row)
                now = datetime.now().isoformat()
                cursor.execute('INSERT INTO users (user_id, language, created_at, last_active, eco_points) VALUES (?, ?, ?, ?, ?)', (user_id, language, now, now, 0))
                conn.commit()
                return {'user_id': user_id, 'language': language, 'created_at': now, 'last_active': now, 'eco_points': 0}
        except Exception as e:
            logger.exception(f"Error get_or_create_user: {e}")
            return None

    def record_classification(self, user_id: str, category: str, confidence: float, image_path: str = None, is_correct: Optional[bool] = None, feedback: str = None) -> bool:
        try:
            with _get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO classifications (user_id, category, confidence, image_path, is_correct, feedback, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime("now","localtime"))
                ''', (user_id, category, confidence, image_path, 1 if is_correct else 0 if is_correct == False else None, feedback))
                if is_correct:
                    cursor.execute('UPDATE users SET eco_points = eco_points + 1 WHERE user_id = ?', (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.exception(f"Error record_classification: {e}")
            return False

    def get_user_stats(self, user_id: str) -> Dict:
        try:
            with _get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as cnt FROM classifications WHERE user_id = ?', (user_id,))
                total = cursor.fetchone()['cnt']
                cursor.execute('SELECT COUNT(*) as cnt FROM classifications WHERE user_id = ? AND is_correct = 1', (user_id,))
                correct = cursor.fetchone()['cnt']
                accuracy = (correct / total * 100) if total > 0 else 0
                cursor.execute("SELECT category, COUNT(*) as c FROM classifications WHERE user_id = ? GROUP BY category ORDER BY c DESC LIMIT 1", (user_id,))
                row = cursor.fetchone()
                most_common = row['category'] if row else None
                cursor.execute('SELECT eco_points FROM users WHERE user_id = ?', (user_id,))
                ep = cursor.fetchone()
                eco_points = ep['eco_points'] if ep else 0
                return {'total_classifications': total, 'correct_classifications': correct, 'accuracy_rate': accuracy, 'most_common_category': most_common or '無', 'eco_points': eco_points}
        except Exception as e:
            logger.exception(f"Error get_user_stats: {e}")
            return {'total_classifications': 0, 'correct_classifications': 0, 'accuracy_rate': 0, 'most_common_category': '無', 'eco_points': 0}
