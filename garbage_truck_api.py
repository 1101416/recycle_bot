# garbage_truck_api.py
"""
新北市垃圾車路線 / 清運時間查詢（取代高雄版）
- 預設使用 data.ntpc.gov.tw 的 dataset id edc3ad26-8ae7-4916-a00b-bc6048d19bf8
- 會嘗試取得 JSON（/json），若失敗可 fallback 讀取 local cache 或產生 synthetic fallback
- 支援環境變數覆寫：
    NTPC_GARBAGE_API_URL    : API endpoint (若你想改成 xml，請直接指定完整 URL)
    NTPC_CACHE_PATH         : 快取路徑 (預設 /tmp/ntpc_schedule_cache.json)
    NTPC_TIMEOUT_SEC        : requests timeout (秒)
    NTPC_RETRY_TOTAL        : requests retry 次數
"""

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

# 預設 API（取 JSON）
DEFAULT_NTPC_API_JSON = "https://data.ntpc.gov.tw/api/datasets/edc3ad26-8ae7-4916-a00b-bc6048d19bf8/json"
# 你也可以指定 xml endpoint: ".../xml"
NTPC_API_URL = os.getenv("NTPC_GARBAGE_API_URL", DEFAULT_NTPC_API_JSON)

CACHE_PATH = os.getenv("NTPC_CACHE_PATH", "/tmp/ntpc_schedule_cache.json")
TIMEOUT_SEC = int(os.getenv("NTPC_TIMEOUT_SEC", "15"))
RETRY_TOTAL = int(os.getenv("NTPC_RETRY_TOTAL", "3"))
RETRY_BACKOFF = float(os.getenv("NTPC_RETRY_BACKOFF", "0.8"))
USE_SYNTHETIC_FALLBACK = os.getenv("NTPC_USE_SYNTH_FALLBACK", "true").lower() not in ("0","false","no")

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

# distance util
def haversine_distance_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
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

def _extract_items_from_json(json_obj: Any) -> List[Dict]:
    # dataset 可能回 list 或 dict 裡包含 list
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
    """
    若 API 回 XML，我們嘗試用簡單方式把每一筆 node 變成 dict。
    此函式不是萬用 XML parser，但能處理常見 element list。
    """
    try:
        root = ET.fromstring(text)
    except Exception:
        return []
    items = []
    # 尋找子節點層（最常見是根下有多個 item）
    for child in root:
        # child 可能包含多個欄位
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

class NewTaipeiTruckAPI:
    def __init__(self, api_url: str = None):
        self.api_url = api_url or NTPC_API_URL
        self.session = _make_session_with_retries()

    def _fetch_api(self) -> Optional[Any]:
        headers = {"User-Agent": "RecycleBot/1.0", "Accept": "application/json, text/xml;q=0.8"}
        try:
            # API 可能支援分頁（size, page），但我們先嘗試一次拉較多筆（size=100）
            params = {"page": 0, "size": 200}
            logger.info("Requesting New Taipei API: %s", self.api_url)
            r = self.session.get(self.api_url, params=params, headers=headers, timeout=TIMEOUT_SEC)
            r.raise_for_status()
            ct = r.headers.get("Content-Type","").lower()
            if "application/json" in ct or r.text.strip().startswith(("[","{")):
                try:
                    return r.json()
                except Exception:
                    logger.exception("JSON parse failed, will attempt XML parse fallback")
                    # try xml parse
                    return _try_parse_xml(r.text)
            else:
                # 嘗試 xml 解析
                items = _try_parse_xml(r.text)
                if items:
                    return items
                # fallback: try json anyway
                try:
                    return r.json()
                except Exception:
                    logger.error("Unknown response format from NTPC API")
                    return None
        except Exception as e:
            try:
                status = getattr(e, "response", None) and getattr(e.response, "status_code", None)
                preview = getattr(e, "response", None) and getattr(e.response, "text", "")[:500]
                logger.error("API request failed: %s status=%s preview=%s", e, status, preview)
            except Exception:
                logger.exception("API request failed")
            return None

    def get_schedules_by_address(self, address: str, radius_m: int = 2000) -> List[Dict]:
        """
        依 address (ex. "新北市三重區...") 回傳 list of {'car','location','time','city'}
        若 API 不可用會使用 local cache；若 cache 無資料且允許，會回 synthetic fallback
        """
        if not address:
            return []

        # parse district & road heuristics
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
            district, road = "", ""

        json_obj = self._fetch_api()
        used_cache = False
        if json_obj is None:
            logger.warning("NTPC API fetch failed, trying cache")
            cached = _load_cache()
            if cached:
                json_obj = cached
                used_cache = True
            else:
                logger.warning("No NTPC cache found")
                if USE_SYNTHETIC_FALLBACK:
                    # create synthetic reference result
                    loc = (f"{district}{road}".strip() or "您附近")
                    return [{
                        "car": "未知車號",
                        "location": f"{loc}（參考）",
                        "time": "※ 非即時資料，僅供參考，請以在地公告為準",
                        "city": "新北市",
                        "_synthetic": True
                    }]
                else:
                    return []

        # 若從 API 得到物件，先儲存快取（若是從快取就不儲存）
        if not used_cache:
            try:
                _save_cache(json_obj, CACHE_PATH)
            except Exception:
                logger.exception("Save cache failed")

        items = _extract_items_from_json(json_obj)
        if not items:
            logger.warning("No items extracted from NTPC API or cache")
            if USE_SYNTHETIC_FALLBACK:
                return [{
                    "car": "未知車號",
                    "location": f"{(district+road).strip() or '您附近'}（參考）",
                    "time": "※ 非即時資料，僅供參考，請以在地公告為準",
                    "city": "新北市",
                    "_synthetic": True
                }]
            return []

        # New Taipei dataset 欄位命名可能不同：試著找出區域與點位名稱與時間欄位
        results = []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                # 常見可能欄位
                area = _get_field_case_insensitive(it, ['行政區','AREA','area','district','區域'])
                caption = _get_field_case_insensitive(it, ['路線名稱','caption','Caption','location','Location','name','名稱'])
                # 時間或收運時間欄位
                time_field = _get_field_case_insensitive(it, ['收運時間','time','Time','收運時段','service_time','timetable','清運時間'])
                car_field = _get_field_case_insensitive(it, ['車牌號碼','car_no','car','車號','車牌'])

                # 根據解析結果做包含比對（容錯）
                area_ok = True if not district else (area and district in str(area))
                road_ok = True if not road else (caption and road in str(caption))

                if area_ok and road_ok:
                    result = {
                        "car": car_field or "未知車號",
                        "location": str(caption or _get_field_case_insensitive(it, ['地址','address','Address'], default='未知地點')),
                        "time": str(time_field or ""),
                        "city": "新北市"
                    }
                    # 標註來源
                    if used_cache:
                        result["_from_cache"] = True
                    results.append(result)
            except Exception:
                logger.exception("Failed to parse NTPC item: %s", it)
                continue

        logger.info("NTPC: found %d matching items for address '%s' (district='%s' road='%s')",
                    len(results), address, district, road)
        if not results and USE_SYNTHETIC_FALLBACK:
            return [{
                "car": "未知車號",
                "location": f"{(district+road).strip() or '您附近'}（參考）",
                "time": "※ 非即時資料，僅供參考，請以在地公告為準",
                "city": "新北市",
                "_synthetic": True
            }]
        return results
