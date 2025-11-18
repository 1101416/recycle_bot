# 檔案: garbage_truck_api.py
# (此版本 v4.2 已修正「今日狀態」的時區問題)

import os
import json
import logging
import math
from typing import List, Dict, Any, Optional
from datetime import datetime
# --- vvv 新增 import vvv ---
try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:
    # Python 3.8 or older (fallback)
    from backports.zoneinfo import ZoneInfo
# --- ^^^ 新增 import ^^^ ---

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# ... (DEFAULT_NTPC_API_JSON, CACHE_PATH, ... CACHE_MAX_AGE_SECONDS 保持不變) ...
DEFAULT_NTPC_API_JSON = os.getenv("NTPC_GARBAGE_API_URL","https://data.ntpc.gov.tw/api/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8/json")
CACHE_PATH = os.getenv("NTPC_CACHE_PATH", "/data/ntpc_schedule_cache.json")
TIMEOUT_SEC = int(os.getenv("NTPC_TIMEOUT_SEC", "15"))
RETRY_TOTAL = int(os.getenv("NTPC_RETRY_TOTAL", "3"))
RETRY_BACKOFF = float(os.getenv("NTPC_RETRY_BACKOFF", "0.8"))
USE_SYNTHETIC_FALLBACK = os.getenv("NTPC_USE_SYNTH_FALLBACK", "true").lower() not in ("0","false","no")
CACHE_MAX_AGE_SECONDS = 86400 
TAIWAN_TZ = ZoneInfo("Asia/Taipei") # <--- 新增台灣時區變數

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
    # ... (__init__, _fetch_api, force_update_cache, _get_all_data 保持不變) ...
    def __init__(self, api_url: str = None):
        self.api_url = api_url or DEFAULT_NTPC_API_JSON
        self.session = _make_session_with_retries()
        self.all_data_cache = None 
    def _fetch_api(self) -> Optional[List[Dict]]:
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
    def force_update_cache(self) -> bool:
        logger.info("Scheduler triggered: Forcing cache update...")
        items = self._fetch_api()
        if items:
            _save_cache(items, CACHE_PATH)
            self.all_data_cache = items 
            logger.info("Cache update successful. %d items saved.", len(items))
            return True
        else:
            logger.error("Cache update failed: _fetch_api() returned None.")
            return False
    def _get_all_data(self) -> Optional[List[Dict]]:
        if self.all_data_cache:
             logger.info("Loading NTPC data from memory cache.")
             return self.all_data_cache
        items = None
        if os.path.exists(CACHE_PATH):
            try:
                file_mod_time = os.path.getmtime(CACHE_PATH)
                if (datetime.now().timestamp() - file_mod_time) < CACHE_MAX_AGE_SECONDS:
                    logger.info(f"Cache file is fresh (under {CACHE_MAX_AGE_SECONDS}s old). Loading from cache file.")
                    items = _load_cache(CACHE_PATH)
                else:
                    logger.info(f"Cache file is stale (over {CACHE_MAX_AGE_SECONDS}s old).")
            except Exception as e:
                logger.warning(f"Could not read cache file mtime or load cache: {e}.")
        if items is None:
            logger.warning("No valid cache found or cache is stale. Fetching from API (this may take ~2 minutes)...")
            items = self._fetch_api()
            if items:
                _save_cache(items, CACHE_PATH)
            else:
                logger.error("Failed to fetch new data from API and no valid cache available.")
                return None
        if items:
            self.all_data_cache = items
        return items

    # --- vvv 請用這個「已修正時區」的版本取代舊的 _parse_truck_item vvv ---
    def _parse_truck_item(self, it: Dict, distance: Optional[int] = None) -> Dict:
        """
        (v4.2) 從原始 item 中提取所需欄位，並解析「今日收運狀態」(已修正時區)。
        """
        
        # 1. 取得「台灣時間」的今日星期幾 (0=Mon, 6=Sun)
        today_weekday = datetime.now(tz=TAIWAN_TZ).weekday() # <--- 修正處
        day_map = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        today_key = day_map[today_weekday] # e.g., 'monday'

        # 2. 建立要檢查的欄位名稱
        garbage_field = f"garbage{today_key}"
        recycling_field = f"recycling{today_key}"
        foodscraps_field = f"foodscraps{today_key}"

        # 3. 檢查 'Y'/'N' 狀態
        collects_garbage = _get_field_case_insensitive(it, [garbage_field], 'N') == 'Y'
        collects_recycling = _get_field_case_insensitive(it, [recycling_field], 'N') == 'Y'
        collects_foodscraps = _get_field_case_insensitive(it, [foodscraps_field], 'N') == 'Y'
        
        today_status = {
            'garbage': collects_garbage,
            'recycling': collects_recycling,
            'foodscraps': collects_foodscraps
        }

        # 4. 提取其他顯示欄位
        linename_field = _get_field_case_insensitive(it, ['linename', '路線名稱']) or "未知路線"
        caption = _get_field_case_insensitive(it, ['name', '清運點名稱']) or _get_field_case_insensitive(it, ['路線名稱'], default='未知地點')
        time_field = _get_field_case_insensitive(it, ['time', '表定時間']) or ""
        city_field = _get_field_case_insensitive(it, ['city', '行政區']) or "新北市"

        # 5. 組合回傳結果
        res = {
            "linename": str(linename_field),
            "location": str(caption),
            "time": str(time_field),
            "city": str(city_field),
            "today_status": today_status
        }
        if distance is not None:
            res["_distance_m"] = int(distance)
            
        return res
    # --- ^^^ 修正結束 ^^^ ---

    # ... (get_schedules_by_location, get_schedules_by_address 保持不變) ...
    def get_schedules_by_location(self, lat: float, lng: float, radius_m: int = 2000, max_results: int = 8) -> List[Dict]:
        items = self._get_all_data()
        if not items:
            logger.warning("No NTPC data available (fetch failed and no cache).")
            if USE_SYNTHETIC_FALLBACK:
                return [{"linename": "未知路線", "location": "您附近（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True, "today_status": {}}]
            return []
        proximity_results = []
        for it in items:
            if not isinstance(it, dict): continue
            latlon = _try_extract_latlon(it)
            if latlon:
                try:
                    d = haversine_distance_m(lat, lng, latlon[0], latlon[1])
                    if d <= radius_m:
                        res = self._parse_truck_item(it, distance=d)
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
        if not address: return []
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
                return [{"linename": "未知路線", "location": f"{(district+road).strip() or '您附近'}（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True, "today_status": {}}]
            return []
        results = []
        for it in items:
            if not isinstance(it, dict): continue
            try:
                area = _get_field_case_insensitive(it, ['city', '行政區'])
                caption = _get_field_case_insensitive(it, ['name', '清運點名稱']) or _get_field_case_insensitive(it, ['linename', '路線名稱'])
                area_ok = True if not district else (area and district in str(area))
                road_ok = True if not road else (caption and road in str(caption))
                if area_ok and road_ok:
                    res = self._parse_truck_item(it)
                    results.append(res)
            except Exception:
                logger.exception("Failed parse item: %s", it)
                continue
        if not results and USE_SYNTHETIC_FALLBACK:
            return [{"linename": "未知路線", "location": f"{(district+road).strip() or '您附近'}（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True, "today_status": {}}]
        return results
