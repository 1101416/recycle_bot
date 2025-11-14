# 檔案: garbage_truck_api.py
# (此版本 v2.0 已修正分頁邏輯，可抓取所有資料)

import os
import json
import logging
import math
from typing import List, Dict, Any, Optional

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
        # 如果 API 回傳的是單一物件而非列表
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

# --- ( _get_field_case_insensitive, _try_extract_latlon 保持不變 ) ---
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
    """
    嘗試從 item 中抽出 (lat, lng)；支援各種常見欄位與 geometry (coordinates)
    回傳 (lat, lng) 或 None
    """
    # 常見欄位
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
    # geometry coordinate (可能為 [lon,lat])
    geom = _get_field_case_insensitive(it, ['geometry','Geometry','geom','location'], default=None)
    if isinstance(geom, dict):
        coords = geom.get('coordinates') or geom.get('coordinate') or geom.get('coords')
        if isinstance(coords, (list,tuple)) and len(coords) >= 2:
            try:
                # 常見為 [lng, lat]
                lng = float(coords[0]); lat = float(coords[1])
                return (lat, lng)
            except Exception:
                pass
    # 有些 API 把 lat/lon 放在同一個字串欄位 "位置" 中，用逗號分隔，嘗試解析
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
                        # sometimes order is lng,lat
                        lon = float(parts[0].strip()); lat = float(parts[1].strip())
                        return (lat, lon)
                    except Exception:
                        pass
    return None
# --- ( _get_field_case_insensitive, _try_extract_latlon 結束 ) ---


class NewTaipeiTruckAPI:
    def __init__(self, api_url: str = None):
        self.api_url = api_url or DEFAULT_NTPC_API_JSON
        self.session = _make_session_with_retries()

    # --- vvv 這裡是主要修改處 vvv ---
    def _fetch_api(self) -> Optional[List[Dict]]:
        """
        (v2.0) 抓取所有分頁的資料並合併。
        回傳合併後的 items 列表，或在失敗時回傳 None。
        """
        headers = {"User-Agent": "RecycleBot/1.0", "Accept": "application/json, text/xml;q=0.8"}
        all_items: List[Dict] = []
        page = 0
        
        # API 最大筆數似乎限制在 1000，我們用 500 比較保險
        page_size = 500 
        
        # 新增迴圈來處理分頁
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
                            raw_page_data = r.json() # 再次嘗試 JSON
                        except Exception:
                            logger.error("Unknown NTPC API response format (Page %d)", page)
                            # 如果第一頁就解析失敗，才回傳 None
                            if page == 0:
                                return None
                            # 如果是後續頁面失敗，至少回傳目前已抓到的
                            break 
                
                if raw_page_data is None:
                    if page == 0:
                        return None
                    break

                # 從該頁的 raw data 中提取 items 列表
                page_items = _extract_items_from_json(raw_page_data)
                
                # 如果 API 回傳空列表，表示已經沒有更多資料了
                if not page_items:
                    logger.info("Reached end of data at page %d.", page)
                    break
                
                all_items.extend(page_items)
                
                # 如果回傳的資料筆數小於要求的筆數，也代表是最後一頁了
                if len(page_items) < page_size:
                    logger.info("Last page detected (items %d < size %d) at page %d.", len(page_items), page_size, page)
                    break

                page += 1
                
                # 安全閥：防止無限迴圈 (26821 筆 / 500 = 54 頁，設 100 頁綽綽有餘)
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
                
                # 如果第一頁就抓取失敗，回傳 None
                if page == 0:
                    return None
                # 如果是中途失敗，至少回傳目前已有的資料
                else:
                    logger.warning("Returning %d items fetched before failure.", len(all_items))
                    break
        
        if not all_items:
            logger.warning("NTPC API returned no items in total.")
            return None
            
        logger.info("Fetched a total of %d items from NTPC API.", len(all_items))
        return all_items
    # --- ^^^ 這裡是主要修改處 ^^^ ---


    def get_schedules_by_location(self, lat: float, lng: float, radius_m: int = 2000, max_results: int = 8) -> List[Dict]:
        """
        以經緯度做篩選（主方法）。
        """
        # 1) 先抓 API 或快取
        
        # --- vvv 修改處 vvv ---
        # _fetch_api() 現在會回傳 items 列表或 None
        items = self._fetch_api() 
        # --- ^^^ 修改處 ^^^ ---
        
        used_cache = False
        if items is None:
            logger.warning("NTPC API fetch failed, trying cache")
            cached = _load_cache()
            if cached:
                # 假設快取中儲存的是 items 列表
                items = cached 
                used_cache = True
            else:
                logger.warning("No NTPC cache found")
                if USE_SYNTHETIC_FALLBACK:
                    # ... (synthetic fallback 保持不變) ...
                    return [{"car": "未知車號", "location": "您附近（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True}]
                return []

        if not used_cache:
            try:
                # --- vvv 修改處 vvv ---
                _save_cache(items, CACHE_PATH) # 直接儲存 items 列表
                # --- ^^^ 修改處 ^^^ ---
            except Exception:
                logger.exception("Save cache failed")

        # --- vvv 修改處 vvv ---
        # items = _extract_items_from_json(json_obj) # <-- 這行已多餘，刪除
        # --- ^^^ 修改處 ^^^ ---
        
        if not items:
            logger.warning("No items found in NTPC data")
            if USE_SYNTHETIC_FALLBACK:
                 # ... (synthetic fallback 保持不變) ...
                return [{"car": "未知車號", "location": "您附近（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True}]
            return []

        # 2) 先嘗試用座標做 proximity search
        proximity_results = []
        for it in items:
            if not isinstance(it, dict):
                continue
            latlon = _try_extract_latlon(it)
            if latlon:
                try:
                    d = haversine_distance_m(lat, lng, latlon[0], latlon[1])
                    if d <= radius_m:
                        # ... (抽出欄位 保持不變) ...
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
                        if used_cache:
                            res["_from_cache"] = True
                        proximity_results.append(res)
                except Exception:
                    logger.exception("Distance calc failed for item: %s", it)
                    continue

        if proximity_results:
            # ... (排序 保持不變) ...
            proximity_results.sort(key=lambda x: x["_distance_m"])
            logger.info("Found %d proximity results", len(proximity_results))
            return proximity_results[:max_results]

        # 3) Fallback
        logger.info("No proximity results found (no coords or outside radius). Returning empty to let caller fallback to address match.")
        return []


    def get_schedules_by_address(self, address: str, radius_m: int = 2000) -> List[Dict]:
        """
        保留 address-based 查詢（較不精準）。
        """
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

        # --- vvv 修改處 (同上) vvv ---
        items = self._fetch_api()
        used_cache = False
        if items is None:
            cached = _load_cache()
            if cached:
                items = cached
                used_cache = True
            else:
                if USE_SYNTHETIC_FALLBACK:
                     # ... (synthetic fallback 保持不變) ...
                    return [{"car": "未知車號", "location": f"{(district+road).strip() or '您附近'}（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True}]
                return []

        if not used_cache:
            try:
                _save_cache(items, CACHE_PATH)
            except Exception:
                logger.exception("Save cache failed")

        # items = _extract_items_from_json(json_obj) # <-- 這行已多餘，刪除
        # --- ^^^ 修改處 (同上) ^^^ ---

        results = []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                # ... (欄位比對 保持不變) ...
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
             # ... (synthetic fallback 保持不變) ...
            return [{"car": "未知車號", "location": f"{(district+road).strip() or '您附近'}（參考）", "time": "※ 非即時資料，僅供參考", "city": "新北市", "_synthetic": True}]
        return results
