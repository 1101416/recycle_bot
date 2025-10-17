# kao_debug.py
import requests
import math
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kao_debug")

KAOHSIUNG_API_URL = "https://api.kcg.gov.tw/api/service/Get/14fe516d-ac62-4905-9325-70daae7616bd"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (KaohsiungClient/1.0)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    # "Referer": "https://data.kcg.gov.tw/"  # 如果需要可打開
}

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def extract_list_from_payload(payload: Any) -> List[Dict]:
    # 若 payload 已經是 list
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    # 常見 container keys
    for k in ("data", "Data", "records", "result", "items", "rows"):
        v = payload.get(k)
        if isinstance(v, list):
            return v
    # 嘗試尋找任何 value 為 list
    for v in payload.values():
        if isinstance(v, list):
            return v
    return []

def parse_latlon(truck: Dict[str, Any]):
    lat_keys = ("lat", "latitude", "y", "Y", "緯度", "Lat", "LAT", "car_lat")
    lon_keys = ("lng", "longitude", "x", "X", "經度", "Lon", "LON", "car_lon")
    lat_val = None
    lon_val = None
    for k in lat_keys:
        if k in truck and truck[k] not in (None, "", "NULL"):
            lat_val = truck[k]; break
    for k in lon_keys:
        if k in truck and truck[k] not in (None, "", "NULL"):
            lon_val = truck[k]; break
    if lat_val is None or lon_val is None:
        return None
    try:
        return float(lat_val), float(lon_val)
    except (ValueError, TypeError):
        return None

def debug_fetch():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        r = s.get(KAOHSIUNG_API_URL, timeout=15)
    except Exception as e:
        logger.error("HTTP request failed: %s", e)
        return

    logger.info("status_code: %s", r.status_code)
    logger.info("content-type: %s", r.headers.get('Content-Type'))
    text = r.text or ""
    logger.info("response text (first 1200 chars):\n%s", text[:1200])

    # 嘗試解析 JSON
    payload = None
    try:
        payload = r.json()
        logger.info("response parsed as JSON (type=%s)", type(payload))
    except Exception as e:
        logger.warning("response.json() failed: %s", e)
        # 如果不是 JSON 就早點回來除錯
        return

    all_trucks = extract_list_from_payload(payload)
    logger.info("extracted %d items from payload", len(all_trucks))

    # 印出前 5 筆的欄位鍵與嘗試解析出 lat/lon
    for i, t in enumerate(all_trucks[:5]):
        logger.info("---- item %d raw keys: %s", i, list(t.keys()) if isinstance(t, dict) else type(t))
        latlon = parse_latlon(t) if isinstance(t, dict) else None
        logger.info("parsed latlon: %s", latlon)
        # 嘗試找車牌或車號欄位
        maybe_car = None
        for k in ("car", "車牌", "car_no", "carno", "車號", "vehicle_no"):
            if isinstance(t, dict) and k in t:
                maybe_car = t.get(k); break
        logger.info("maybe car: %s", maybe_car)
        logger.info("raw item preview: %s", str(t)[:500])

if __name__ == "__main__":
    debug_fetch()
