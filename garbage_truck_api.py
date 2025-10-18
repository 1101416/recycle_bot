# garbage_truck_api.py
"""
改良版：加入 requests Retry、exponential backoff，以及本地快取備援。
使用情境：
- 若能連到 API：會回傳最新資料並把 JSON 存到快取檔（預設 kcg_schedule_cache.json）
- 若連不到 API：會讀取快取檔並用快取資料回應（若快取存在）
"""

import os
import json
import logging
import math
import time
from typing import List, Dict, Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

KAOHSIUNG_SCHEDULE_API_URL = os.getenv(
    "KCG_GARBAGE_API_URL",
    "https://api.kcg.gov.tw/Api/Service/Get/14fe516d-ac62-4905-9325-70daae7616bd"
)

# 快取檔（可在環境變數指定）
CACHE_PATH = os.getenv("KCG_LOCAL_CACHE", "/tmp/kcg_schedule_cache.json")

# Retry 設定
RETRY_TOTAL = int(os.getenv("KCG_RETRY_TOTAL", "3"))
RETRY_BACKOFF_FACTOR = float(os.getenv("KCG_RETRY_BACKOFF", "0.8"))
TIMEOUT_SEC = int(os.getenv("KCG_TIMEOUT_SEC", "15"))  # connect+read timeout（秒）

def _make_session_with_retries(total=RETRY_TOTAL, backoff=RETRY_BACKOFF_FACTOR) -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=total,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET","POST"])
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

# Haversine：計算兩點距離（公尺）
def haversine_distance_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _extract_items_from_response(json_obj: Any) -> List[Dict]:
    if isinstance(json_obj, dict):
        for key in ("data","Data","records","Records","value","Value","results","Results"):
            if key in json_obj and isinstance(json_obj[key], list):
                return json_obj[key]
        for k,v in json_obj.items():
            if isinstance(v, list):
                return v
        return [json_obj]
    elif isinstance(json_obj, list):
        return json_obj
    else:
        return []

def _get_field_case_insensitive(obj: Dict, candidates: List[str], default=None):
    if not isinstance(obj, dict):
        return default
    for c in candidates:
        if c in obj:
            return obj[c]
    # lower-case 比對
    lower_map = {k.lower(): k for k in obj.keys()}
    for c in candidates:
        lc = c.lower()
        if lc in lower_map:
            return obj[lower_map[lc]]
    return default

def _save_cache(json_obj: Any, path: str = CACHE_PATH):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(json_obj, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved API cache to {path}")
    except Exception:
        logger.exception("Failed to save API cache")

def _load_cache(path: str = CACHE_PATH) -> Optional[Any]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Loaded API cache from {path}")
            return data
    except Exception:
        logger.exception("Failed to load API cache")
    return None

class GarbageTruckAPI:
    def __init__(self, api_url: str = None):
        self.api_url = api_url or KAOHSIUNG_SCHEDULE_API_URL
        self.session = _make_session_with_retries()

    def _fetch_api_json(self) -> Optional[Any]:
        headers = {"User-Agent": "GreenLineBot/1.0"}
        try:
            logger.info(f"Requesting Kaohsiung API: {self.api_url} (timeout={TIMEOUT_SEC})")
            r = self.session.get(self.api_url, headers=headers, timeout=TIMEOUT_SEC)
            r.raise_for_status()
            # 嘗試解析 JSON
            return r.json()
        except Exception as e:
            # 記錄詳細資訊（status code / text if present）
            try:
                status = getattr(e, "response", None) and getattr(e.response, "status_code", None)
                text_preview = getattr(e, "response", None) and getattr(e.response, "text", "")[:1000]
                logger.error(f"API request failed: {e} status={status} preview={text_preview}")
            except Exception:
                logger.exception("API request failed (no response available)")
            return None

    def get_schedules_by_address(self, address: str, radius_m: int = 2000) -> List[Dict]:
        """
        主要入口：給定 address（line 的 event.message.address），回傳 list of schedules
        回傳格式每筆 dict: {'car','location','time','city'}
        """
        if not address:
            return []

        # 解析 district 與 road（heuristics）
        try:
            tmp = address.replace("台灣","").replace("臺灣","")
            parts = tmp.split('市')
            addr_after = parts[1] if len(parts) >= 2 else tmp
            district = addr_after.split('區')[0] + '區' if '區' in addr_after else ''
            road = ""
            for kw in ['路','街','大道','巷']:
                if kw in addr_after:
                    try:
                        road = addr_after.split(kw)[0].split('區')[-1] + kw
                    except Exception:
                        road = ""
                    break
        except Exception:
            logger.exception("Address parse error")
            district = ""
            road = ""

        # 先嘗試呼叫 API（若失敗則使用快取）
        json_obj = self._fetch_api_json()
        if json_obj is None:
            logger.warning("API fetch returned None — trying local cache fallback")
            cached = _load_cache()
            if cached is None:
                logger.warning("No local cache available. Returning empty result.")
                return []
            items = _extract_items_from_response(cached)
        else:
            items = _extract_items_from_response(json_obj)
            # 儲存快取（非阻塞）
            try:
                _save_cache(json_obj)
            except Exception:
                pass

        if not items:
            logger.warning("No items extracted from API or cache")
            return []

        matching = []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                point_area = _get_field_case_insensitive(it, ['area','Area','行政區','district'], default=None)
                point_caption = _get_field_case_insensitive(it, ['caption','Caption','名稱','Name','location','Location'], default=None)

                today_s = _get_field_case_insensitive(it, ['today_s','Today_s','start_time','StartTime','todayStart','Start'], default=None)
                today_e = _get_field_case_insensitive(it, ['today_e','Today_e','end_time','EndTime','todayEnd','End'], default=None)
                if not today_s and not today_e:
                    t_single = _get_field_case_insensitive(it, ['time','Time','預計時間','time_text'], default=None)
                    if t_single:
                        today_s = t_single
                        today_e = ""

                car_license = _get_field_case_insensitive(it, ['car_licence','carLicence','carNo','car','車號'], default='未知車號')

                # 簡單的文字包含比對（容錯）
                area_ok = True if not district else (point_area and district in str(point_area))
                road_ok = True if not road else (point_caption and road in str(point_caption))

                if area_ok and road_ok:
                    schedule_info = {
                        'car': car_license,
                        'location': str(point_caption) if point_caption else str(_get_field_case_insensitive(it, ['address','Address','addr'], default='未知地點')),
                        'time': f"{today_s or ''}{(' - ' + today_e) if today_e else ''}".strip(),
                        'city': '高雄市'
                    }
                    matching.append(schedule_info)
            except Exception:
                logger.exception(f"Failed to parse item: {it}")
                continue

        logger.info(f"get_schedules_by_address -> found {len(matching)} entries for address '{address}' (district='{district}', road='{road}')")
        return matching
