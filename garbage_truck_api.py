# 檔案: garbage_truck_api.py
# (此版本 v4.0 已修正為「排程器更新」邏輯 + 修正「未知車號」Bug)

import os
import json
import logging
import math
from typing import List, Dict, Any, Optional
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

DEFAULT_NTPC_API_JSON = os.getenv(
    "NTPC_GARBAGE_API_URL",
    "https://data.ntpc.gov.tw/api/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8/json"
)

# --- vvv 修改處：使用 Render 永久硬碟路徑 vvv ---
CACHE_PATH = os.getenv("NTPC_CACHE_PATH", "/data/ntpc_schedule_cache.json")
# --- ^^^ 修改處 ^^^ ---

TIMEOUT_SEC = int(os.getenv("NTPC_TIMEOUT_SEC", "15"))
RETRY_TOTAL = int(os.getenv("NTPC_RETRY_TOTAL", "3"))
RETRY_BACKOFF = float(os.getenv("NTPC_RETRY_BACKOFF", "0.8"))
USE_SYNTHETIC_FALLBACK = os.getenv("NTPC_USE_SYNTH_FALLBACK", "true").lower() not in ("0","false","no")
CACHE_MAX_AGE_SECONDS = 87000 # 24 小時 + 10 分鐘緩衝

# ... ( _make_session_with_retries, haversine_distance_m, _save_cache, _load_cache 保持不變 ) ...
def _make_session_with_retries(total=RETRY_TOTAL, backoff=RETRY_BACKOFF) -> requests.Session:
    s = requests.Session()
    retries = Retry(total=total, backoff_factor=backoff, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=frozenset(["GET","POST"]))
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
# ... ( _extract_items_from_json, _try_parse_xml, _get_field_case_insensitive, _try_extract_latlon 保持不變 ) ...
def _extract_items_from_json(json_obj: Any) -> List[Dict]:
    if isinstance(json_obj, list): return json_obj
    if isinstance(json_obj, dict):
        for k in ("data","records","value","results","items"):
            if k in json_obj and isinstance(json_obj[k], list): return json_obj[k]
        for k,v in json_obj.items():
            if isinstance(v, list): return v
        return [json_obj]
    return []
def _try_parse_xml(text: str) -> List[Dict]:
    try: root = ET.fromstring(text)
    except Exception: return []
    items = []
    for child in root:
        item = {}
        for sub in child: item[sub.tag] = sub.text
        if item: items.append(item)
    return items
def _get_field_case_insensitive(obj: Dict, candidates: List[str], default=None):
    if not isinstance(obj, dict): return default
    for c in candidates:
        if c in obj: return obj[c]
    lower_map = {k.lower(): k for k in obj.keys()}
    for c in candidates:
        lc = c.lower()
        if lc in lower_map: return obj[lower_map[lc]]
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
                    except Exception: continue
    geom = _get_field_case_insensitive(it, ['geometry','Geometry','geom','location'], default=None)
    if isinstance(geom, dict):
        coords = geom.get('coordinates') or geom.get('coordinate') or geom.get('coords')
        if isinstance(coords, (list,tuple)) and len(coords) >= 2:
            try:
                lng = float(coords[0]); lat = float(coords[1])
                return (lat, lng)
            except Exception: pass
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
                    except Exception: pass
    return None

class NewTaipeiTruckAPI:
    def __init__(self, api_url: str = None):
        self.api_url = api_url or DEFAULT_NTPC_API_JSON
        self.session = _make_session_with_retries()
        self.all_data_cache = None 

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
                    try: raw_page_data = r.json()
                    except Exception: raw_page_data = _try_parse_xml(r.text)
                else:
                    items_xml = _try_parse_xml(r.text)
                    if items_xml: raw_page_data = items_xml
                    else:
                        try: raw_page_data = r.json() 
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

    # --- vvv 新增函式：專門給排程器呼叫 vvv ---
    def force_update_cache(self) -> bool:
        """
        (v4.0) 由排程器呼叫，強制下載 API 資料並寫入快取。
        """
        logger.info("Scheduler triggered: Forcing cache update...")
        items = self._fetch_api()
        
        if items:
            _save_cache(items, CACHE_PATH)
            self.all_data_cache = items # 更新記憶體快取
            logger.info("Cache update successful. %d items saved.", len(items))
            return True
        else:
            logger.error("Cache update failed: _fetch_api() returned None.")
            return False
    # --- ^^^ 新增函式 ^^^ ---

    def _get_all_data(self) -> Optional[List[Dict]]:
        """
        (v4.0) 檢查快取，如果過期或不存在，才呼叫 _fetch_api()
        """
        # 1. 檢查記憶體快取
        if self.all_data_cache:
             logger.info("Loading NTPC data from memory cache.")
             return self.all_data_cache

        # 2. 檢查檔案快取
        items = None
        if os.path.exists(CACHE_PATH):
            try:
                file_mod_time = os.path.getmtime(CACHE_PATH)
                # 檢查快取是否在 24 小時內
                if (datetime.now().timestamp() - file_mod_time) < CACHE_MAX_AGE_SECONDS:
                    logger.info(f"Cache file is fresh (under {CACHE_MAX_AGE_SECONDS}s old). Loading from cache file.")
                    items = _load_cache(CACHE_PATH)
                else:
                    logger.info(f"Cache file is stale (over {CACHE_MAX_AGE_SECONDS}s old).")
            except Exception as e:
                logger.warning(f"Could not read cache file mtime or load cache: {e}.")
        
        # 3. 如果快取不存在或已過期，觸發下載 (這是使用者的後備方案)
        if items is None:
            logger.warning("No valid cache found or cache is stale. Fetching from API (this may take ~2 minutes)...")
            items = self._fetch_api()
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
        """ (v4.0) 以經緯度做篩選 """
        
        items = self._get_all_data()
        
        if not items:
            logger.warning("No NTPC data available (fetch failed and no cache).")
            if USE_SYNTHETIC_FALLBACK:
                return [{"car": "未知車號", "location": "您附近（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True}]
            return []
        
        proximity_results = []
        for it in items:
            if not isinstance(it, dict):
                continue
            latlon = _try_extract_latlon(it)
            if latlon:
                try:
                    d = haversine_distance_m(lat, lng, latlon[0], latlon[1])
                    if d <= radius_m:
                        # --- vvv 修改處：修正「未知車號」 vvv ---
                        linename_field = _get_field_case_insensitive(it, ['linename', '路線名稱']) or "未知路線"
                        # --- ^^^ 修改處 ^^^ ---
                        caption = _get_field_case_insensitive(it, ['路線名稱','caption','Caption','location','name','名稱']) or _get_field_case_insensitive(it, ['地址','address','Address'], default='未知地點')
                        time_field = _get_field_case_insensitive(it, ['收運時間','time','Time','收運時段','service_time','timetable','清運時間']) or ""
                        
                        res = {
                            "linename": str(linename_field), # <--- 修改處
                            "location": str(caption),
                            "time": str(time_field),
                            "city": "新北市",
                            "_distance_m": int(d)
                        }
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
        """ (v4.0) 保留 address-based 查詢 """
        
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

        items = self._get_all_data()

        if not items:
            logger.warning("No NTPC data available (fetch failed and no cache).")
            if USE_SYNTHETIC_FALLBACK:
                return [{"car": "未知車號", "location": f"{(district+road).strip() or '您附近'}（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True}]
            return []
        
        results = []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                area = _get_field_case_insensitive(it, ['行政區','AREA','area','district','區域'])
                caption = _get_field_case_insensitive(it, ['路線名稱','caption','Caption','location','Location','name','名稱'])
                time_field = _get_field_case_insensitive(it, ['收運時間','time','Time','收運時段','service_time','timetable','清運時間'])
                # --- vvv 修改處：修正「未知車號」 vvv ---
                linename_field = _get_field_case_insensitive(it, ['linename', '路線名稱']) or "未知路線"
                # --- ^^^ 修改處 ^^^ ---
                area_ok = True if not district else (area and district in str(area))
                road_ok = True if not road else (caption and road in str(caption))
                if area_ok and road_ok:
                    results.append({
                        "linename": str(linename_field), # <--- 修改處
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
