# 檔案: garbage_truck_api.py
# (此版本 v3.0 已修正為「快取優先」邏輯，每日更新一次)

import os
import json
import logging
import math
from typing import List, Dict, Any, Optional
# --- vvv 新增 import vvv ---
from datetime import datetime
# --- ^^^ 新增 import ^^^ ---

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

DEFAULT_NTPC_API_JSON = os.getenv(
    "NTPC_GARBAGE_API_URL",
    "https://data.ntpc.gov.tw/api/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8/json"
)
CACHE_PATH = os.getenv("NTPC_CACHE_PATH", "/tmp/ntpc_schedule_cache.json")
TIMEOUT_SEC = int(os.getenv("NTPC_TIMEOUT_SEC", "15"))
RETRY_TOTAL = int(os.getenv("NTPC_RETRY_TOTAL", "3"))
RETRY_BACKOFF = float(os.getenv("NTPC_RETRY_BACKOFF", "0.8"))
USE_SYNTHETIC_FALLBACK = os.getenv("NTPC_USE_SYNTH_FALLBACK", "true").lower() not in ("0","false","no")

# --- vvv 新增快取時間 (24 * 60 * 60 = 86400 秒) vvv ---
CACHE_MAX_AGE_SECONDS = 86400 
# --- ^^^ 新增快取時間 ^^^ ---


# --- ( _make_session_with_retries, haversine_distance_m, _save_cache, _load_cache 保持不變 ) ---
def _make_session_with_retries(total=RETRY_TOTAL, backoff=RETRY_BACKOFF) -> requests.Session:
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

def haversine_distance_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _save_cache(obj: Any, path: str = CACHE_PATH):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        logger.info("Saved NTPC cache to %s", path)
    except Exception:
        logger.exception("Failed to save cache")

def _load_cache(path: str = CACHE_PATH) -> Optional[Any]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        logger.exception("Failed to load cache")
    return None
# --- ( _make_session_with_retries, haversine_distance_m, _save_cache, _load_cache 結束 ) ---

# --- ( _extract_items_from_json, _try_parse_xml, _get_field_case_insensitive, _try_extract_latlon 保持不變 ) ---
def _extract_items_from_json(json_obj: Any) -> List[Dict]:
    if isinstance(json_obj, list):
        return json_obj
    if isinstance(json_obj, dict):
        for k in ("data","records","value","results","items"):
            if k in json_obj and isinstance(json_obj[k], list):
                return json_obj[k]
        for k,v in json_obj.items():
            if isinstance(v, list):
                return v
        return [json_obj]
    return []

def _try_parse_xml(text: str) -> List[Dict]:
    try:
        root = ET.fromstring(text)
    except Exception:
        return []
    items = []
    for child in root:
        item = {}
        for sub in child:
            item[sub.tag] = sub.text
        if item:
            items.append(item)
    return items

def _get_field_case_insensitive(obj: Dict, candidates: List[str], default=None):
    if not isinstance(obj, dict):
        return default
    for c in candidates:
        if c in obj:
            return obj[c]
    lower_map = {k.lower(): k for k in obj.keys()}
    for c in candidates:
        lc = c.lower()
        if lc in lower_map:
            return obj[lower_map[lc]]
    return default

def _try_extract_latlon(it: Dict) -> Optional[tuple]:
    lat_keys = ['lat','latitude','緯度','LAT','Latitude','Y','y']
    lon_keys = ['lng','lon','longitude','經度','LON','LONG','Longitude','X','x']
    for lk in lat_keys:
        if lk in it:
            for ok in lon_keys:
                if ok in it:
                    try:
                        lat = float(it[lk]); lon = float(it[ok])
                        return (lat, lon)
                    except Exception:
                        continue
    geom = _get_field_case_insensitive(it, ['geometry','Geometry','geom','location'], default=None)
    if isinstance(geom, dict):
        coords = geom.get('coordinates') or geom.get('coordinate') or geom.get('coords')
        if isinstance(coords, (list,tuple)) and len(coords) >= 2:
            try:
                lng = float(coords[0]); lat = float(coords[1])
                return (lat, lng)
            except Exception:
                pass
    for candidate in ['位置','position','pos','latlng','LatLng']:
        val = _get_field_case_insensitive(it, [candidate], default=None)
        if isinstance(val, str) and ',' in val:
            parts = val.split(',')
            if len(parts) >= 2:
                try:
                    lat = float(parts[0].strip()); lon = float(parts[1].strip())
                    return (lat, lon)
                except Exception:
                    try:
                        lon = float(parts[0].strip()); lat = float(parts[1].strip())
                        return (lat, lon)
                    except Exception:
                        pass
    return None
# --- ( _extract_items_from_json, _try_parse_xml, _get_field_case_insensitive, _try_extract_latlon 結束 ) ---


class NewTaipeiTruckAPI:
    def __init__(self, api_url: str = None):
        self.api_url = api_url or DEFAULT_NTPC_API_JSON
        self.session = _make_session_with_retries()
        # --- vvv 這裡的 _fetch_api 保持不變 (仍是 v2.0 的分頁下載邏輯) vvv ---
        self.all_data_cache = None # 新增一個實例變數來暫存記憶體中的資料

    def _fetch_api(self) -> Optional[List[Dict]]:
        """ (v2.0) 抓取所有分頁的資料並合併。 """
        headers = {"User-Agent": "RecycleBot/1.0", "Accept": "application/json, text/xml;q=0.8"}
        all_items: List[Dict] = []
        page = 0
        page_size = 500 
        
        while True:
            params = {"page": page, "size": page_size}
            try:
                logger.info("Requesting New Taipei API: %s (Page: %d, Size: %d)", self.api_url, page, page_size)
                r = self.session.get(self.api_url, params=params, headers=headers, timeout=TIMEOUT_SEC)
                r.raise_for_status()
                
                raw_page_data = None
                ct = r.headers.get("Content-Type","").lower()

                if "application/json" in ct or r.text.strip().startswith(("[","{")):
                    try:
                        raw_page_data = r.json()
                    except Exception:
                        logger.exception("JSON parse failed, attempt XML parse")
                        raw_page_data = _try_parse_xml(r.text)
                else:
                    items_xml = _try_parse_xml(r.text)
                    if items_xml:
                        raw_page_data = items_xml
                    else:
                        try:
                            raw_page_data = r.json() 
                        except Exception:
                            logger.error("Unknown NTPC API response format (Page %d)", page)
                            if page == 0: return None
                            break 
                
                if raw_page_data is None:
                    if page == 0: return None
                    break

                page_items = _extract_items_from_json(raw_page_data)
                
                if not page_items:
                    logger.info("Reached end of data at page %d.", page)
                    break
                
                all_items.extend(page_items)
                
                if len(page_items) < page_size:
                    logger.info("Last page detected (items %d < size %d) at page %d.", len(page_items), page_size, page)
                    break

                page += 1
                if page > 100:
                    logger.warning("Reached safety limit (100 pages). Stopping fetch.")
                    break

            except Exception as e:
                try:
                    status = getattr(e, "response", None) and getattr(e.response, "status_code", None)
                    preview = getattr(e, "response", None) and getattr(e.response, "text", "")[:500]
                    logger.error("NTPC API request failed (Page %d): %s status=%s preview=%s", page, e, status, preview)
                except Exception:
                    logger.exception("NTPC API request failed (Page %d)", page)
                
                if page == 0: return None
                else:
                    logger.warning("Returning %d items fetched before failure.", len(all_items))
                    break
        
        if not all_items:
            logger.warning("NTPC API returned no items in total.")
            return None
            
        logger.info("Fetched a total of %d items from NTPC API.", len(all_items))
        return all_items
    # --- ^^^ _fetch_api 保持不變 ^^^ ---

    # --- vvv 這裡是主要修改處 (v3.0 快取邏輯) vvv ---
    def _get_all_data(self) -> Optional[List[Dict]]:
        """
        (v3.0) 檢查檔案快取，如果過期或不存在，才呼叫 _fetch_api()
        """
        # 1. 檢查記憶體快取 (如果伺服器沒重啟)
        if self.all_data_cache:
             logger.info("Loading NTPC data from memory cache.")
             return self.all_data_cache

        # 2. 檢查檔案快取 (如果伺服器重啟)
        used_cache = False
        items = None
        if os.path.exists(CACHE_PATH):
            try:
                file_mod_time = os.path.getmtime(CACHE_PATH)
                # 檢查快取是否在 24 小時 (86400 秒) 內
                if (datetime.now().timestamp() - file_mod_time) < CACHE_MAX_AGE_SECONDS:
                    logger.info(f"Cache file is fresh (under {CACHE_MAX_AGE_SECONDS}s old). Loading from cache file.")
                    items = _load_cache(CACHE_PATH)
                    if items:
                        used_cache = True
                else:
                    logger.info(f"Cache file is stale (over {CACHE_MAX_AGE_SECONDS}s old). Fetching new data.")
            except Exception as e:
                logger.warning(f"Could not read cache file mtime or load cache: {e}. Fetching new data.")
        
        # 3. 如果快取不存在或已過期，才執行 2 分鐘的下載
        if not used_cache:
            logger.info("No valid cache found. Fetching from API (this may take ~2 minutes)...")
            items = self._fetch_api()
            
            # 如果下載成功，寫入快取
            if items:
                _save_cache(items, CACHE_PATH)
            else:
                logger.error("Failed to fetch new data from API and no valid cache available.")
                return None # 確定失敗
        
        # 4. 將資料存入記憶體快取並回傳
        if items:
            self.all_data_cache = items
        return items

    def get_schedules_by_location(self, lat: float, lng: float, radius_m: int = 2000, max_results: int = 8) -> List[Dict]:
        """ (v3.0) 以經緯度做篩選 """
        
        # 1) 呼叫新的快取邏輯函式
        items = self._get_all_data()
        
        if not items:
            logger.warning("No NTPC data available (fetch failed and no cache).")
            if USE_SYNTHETIC_FALLBACK:
                return [{"car": "未知車號", "location": "您附近（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True}]
            return []
        
        # 2) 座標 proximity search (保持不變)
        proximity_results = []
        for it in items:
            if not isinstance(it, dict):
                continue
            latlon = _try_extract_latlon(it)
            if latlon:
                try:
                    d = haversine_distance_m(lat, lng, latlon[0], latlon[1])
                    if d <= radius_m:
                        caption = _get_field_case_insensitive(it, ['路線名稱','caption','Caption','location','name','名稱']) or _get_field_case_insensitive(it, ['地址','address','Address'], default='未知地點')
                        time_field = _get_field_case_insensitive(it, ['收運時間','time','Time','收運時段','service_time','timetable','清運時間']) or ""
                        car_field = _get_field_case_insensitive(it, ['車牌號碼','car_no','car','車號','車牌']) or "未知車號"
                        res = {
                            "car": car_field,
                            "location": str(caption),
                            "time": str(time_field),
                            "city": "新北市",
                            "_distance_m": int(d)
                        }
                        # 標記 _from_cache (現在 _get_all_data 處理了)
                        # res["_from_cache"] = used_cache # (這部分邏輯可以簡化或移除)
                        proximity_results.append(res)
                except Exception:
                    logger.exception("Distance calc failed for item: %s", it)
                    continue

        if proximity_results:
            proximity_results.sort(key=lambda x: x["_distance_m"])
            logger.info("Found %d proximity results", len(proximity_results))
            return proximity_results[:max_results]

        logger.info("No proximity results found (no coords or outside radius). Returning empty to let caller fallback to address match.")
        return []

    def get_schedules_by_address(self, address: str, radius_m: int = 2000) -> List[Dict]:
        """ (v3.0) 保留 address-based 查詢 """
        
        if not address:
            return []
        # ... (地址解析 保持不變) ...
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

        # 1) 呼叫新的快取邏輯函式
        items = self._get_all_data()

        if not items:
            logger.warning("No NTPC data available (fetch failed and no cache).")
            if USE_SYNTHETIC_FALLBACK:
                return [{"car": "未知車號", "location": f"{(district+road).strip() or '您附近'}（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True}]
            return []
        
        # 2) 文字比對 (保持不變)
        results = []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                area = _get_field_case_insensitive(it, ['行政區','AREA','area','district','區域'])
                caption = _get_field_case_insensitive(it, ['路線名稱','caption','Caption','location','Location','name','名稱'])
                time_field = _get_field_case_insensitive(it, ['收運時間','time','Time','收運時段','service_time','timetable','清運時間'])
                car_field = _get_field_case_insensitive(it, ['車牌號碼','car_no','car','車號','車牌'])
                area_ok = True if not district else (area and district in str(area))
                road_ok = True if not road else (caption and road in str(caption))
                if area_ok and road_ok:
                    results.append({
                        "car": car_field or "未知車號",
                        "location": str(caption or _get_field_case_insensitive(it, ['地址','address'], default='未知地點')),
                        "time": str(time_field or ""),
                        "city": "新北市",
                    })
            except Exception:
                logger.exception("Failed parse item: %s", it)
                continue

        if not results and USE_SYNTHETIC_FALLBACK:
            return [{"car": "未知車號", "location": f"{(district+road).strip() or '您附近'}（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True}]
        return results
    # --- ^^^ 這裡是主要修改處 (v3.0 快取邏輯) ^^^ ---
