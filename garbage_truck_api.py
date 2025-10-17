import requests
import logging
import math
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TAOYUAN_REALTIME_API_URL = "https://route.tyoem.gov.tw/api/get_all_car_location"

class GarbageTruckAPI:
    def __init__(self, timeout: int = 20):
        # 加上常見的 header（Referer 要有，有時也需要 User-Agent / Origin）
        self.headers = {
            "Referer": "https://route.tyoem.gov.tw/",
            "User-Agent": "Mozilla/5.0 (compatible; GarbageTruckClient/1.0)",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": "https://route.tyoem.gov.tw"
        }
        self.timeout = timeout

    def _fetch_all_trucks(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(TAOYUAN_REALTIME_API_URL, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error("HTTP request failed: %s", e)
            raise

        try:
            payload = resp.json()
        except ValueError:
            # 不是 JSON（或 JSON 解析失敗）
            logger.error("Response is not valid JSON; first 500 chars: %s", resp.text[:500])
            raise

        # 常見情形：API 回傳 list，或回傳 dict 包含 key 如 'data','rows','cars' 等
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            # 嘗試常見的 key
            for k in ("data", "rows", "cars", "result", "items", "list"):
                if k in payload and isinstance(payload[k], list):
                    return payload[k]

            # 若某個 value 本身是 list，也取第一個 list
            for v in payload.values():
                if isinstance(v, list):
                    return v

            # 最後嘗試把 dictionary 的 value 轉成 list（若 keys 為數字字串）
            if all(isinstance(k, str) and k.isdigit() for k in payload.keys()):
                return list(payload.values())

        logger.warning("Unexpected JSON structure from Taoyuan API: %s", type(payload))
        return []

    @staticmethod
    def _parse_lat_lon(truck: Dict[str, Any]) -> Optional[tuple]:
        # 嘗試多種可能的欄位名稱
        lat_keys = ("lat", "latitude", "LAT", "Latitude")
        lon_keys = ("lon", "lng", "longitude", "LON", "Longitude", "Lng")

        lat_val = None
        lon_val = None

        for k in lat_keys:
            if k in truck and truck[k] not in (None, ""):
                lat_val = truck[k]
                break
        for k in lon_keys:
            if k in truck and truck[k] not in (None, ""):
                lon_val = truck[k]
                break

        if lat_val is None or lon_val is None:
            return None

        try:
            lat = float(str(lat_val).strip())
            lon = float(str(lon_val).strip())
            return lat, lon
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        # 正確計算球面距離（公裏）
        R = 6371.0  # 地球半徑（km）
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        user_lat = float(latitude)
        user_lon = float(longitude)
        nearby_trucks: List[Dict] = []

        try:
            all_trucks = self._fetch_all_trucks()
        except Exception as e:
            logger.error("Failed fetching trucks: %s", e)
            return []

        if not all_trucks:
            logger.info("No trucks returned from API.")
            return []

        for truck in all_trucks:
            try:
                parsed = self._parse_lat_lon(truck)
                if parsed is None:
                    continue
                lat, lon = parsed

                dist_km = self._haversine_km(user_lat, user_lon, lat, lon)

                if dist_km <= radius_km:
                    # 嘗試抓常見欄位
                    car_no = truck.get("car_no") or truck.get("carno") or truck.get("vehicle_no") or truck.get("車號") or "未知"
                    location = truck.get("address") or truck.get("loc") or truck.get("位置") or truck.get("addr") or "即時位置更新"
                    update_time = truck.get("update_time") or truck.get("time") or truck.get("updated_at") or ""

                    truck_info = {
                        "car": car_no,
                        "location": location,
                        "time": update_time,
                        "city": "桃園市",
                        "distance_km": round(dist_km, 3),
                        "raw": truck  # 若要除錯可以保留原始資料
                    }
                    nearby_trucks.append(truck_info)
            except Exception:
                # 單筆資料解析錯誤不影響整體
                continue

        nearby_trucks.sort(key=lambda x: x["distance_km"])
        logger.info("Found %d nearby garbage trucks.", len(nearby_trucks))
        return nearby_trucks
