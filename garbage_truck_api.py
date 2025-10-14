import requests
import logging
import urllib3
from typing import List, Dict

logger = logging.getLogger(__name__)

# 關閉因 SSL 憑證驗證失敗而產生的警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 六都垃圾車公開資料 API 網址庫 (2025年最終驗證版) ---
CITY_APIS = {
    "taipei": {
        "name": "臺北市",
        "url": "https://data.taipei/api/v1/dataset/a8025D87-2D99-43C6-9E2A-78E56839352F?scope=resourceAquire",
        "parser": "taipei"
    },
    "new_taipei": {
        "name": "新北市",
        "url": "https://data.ntpc.gov.tw/api/datasets/28AB4122-60E1-4065-98E5-AB48A68B3516/json?page=0&size=2000",
        "parser": "new_taipei"
    },
    "taoyuan": {
        "name": "桃園市",
        "url": "https://data.tycg.gov.tw/api/v1/rest/datastore/a1b4714b-fc25-4671-a533-606540c55768?limit=1000",
        "parser": "taoyuan",
        "verify_ssl": False # 特別標記桃園 API 需要忽略 SSL 驗證
    },
    "taichung": {
        "name": "臺中市",
        "url": "https://datacenter.taichung.gov.tw/swagger/OpenData/9188423a-1336-4b13-8822-ea1391b03361",
        "parser": "taichung"
    },
    "tainan": {
        "name": "臺南市",
        "url": "https://data.tainan.gov.tw/api/v2/sql?query=SELECT%20%22CarNo%22,%20%22Lat%22,%20%22Lon%22,%20%22Location%22,%20%22Time%22%20FROM%20%22ebe7c03a-c85c-44c1-884c-389ce542d992%22",
        "parser": "tainan"
    },
    "kaohsiung": {
        "name": "高雄市",
        "url": "https://data.kcg.gov.tw/api/action/datastore_search?resource_id=1999b828-a623-4c07-957e-39a7b94b42b1&limit=2000",
        "parser": "kaohsiung"
    }
}

class GarbageTruckAPI:

    def _parse_data(self, json_data: any, parser_type: str, city_name: str) -> List[Dict]:
        """(強固版) 根據不同縣市的 API 格式，安全地解析並標準化資料"""
        parsed_trucks = []
        records = []
        key_map = {}

        try:
            # 針對不同縣市的 JSON 結構，安全地取出車輛紀錄列表
            if parser_type == "taipei":
                if isinstance(json_data, dict): records = json_data.get('result', {}).get('records', [])
                key_map = {'car': 'car', 'lat': 'lat', 'lon': 'lon', 'location': 'location', 'time': 'time'}
            elif parser_type == "new_taipei":
                if isinstance(json_data, list): records = json_data
                key_map = {'car': 'car', 'lat': 'latitude', 'lon': 'longitude', 'location': 'location', 'time': 'time'}
            elif parser_type == "taoyuan":
                if isinstance(json_data, dict): records = json_data.get('result', {}).get('records', [])
                key_map = {'car': 'Car', 'lat': 'Lat', 'lon': 'Lon', 'location': 'Location', 'time': 'Time'}
            elif parser_type == "taichung":
                if isinstance(json_data, list): records = json_data
                key_map = {'car': 'car_id', 'lat': 'lat', 'lon': 'lng', 'location': 'location', 'time': 'time'}
            elif parser_type == "tainan":
                if isinstance(json_data, dict): records = json_data.get('result', {}).get('records', [])
                key_map = {'car': 'CarNo', 'lat': 'Lat', 'lon': 'Lon', 'location': 'Location', 'time': 'Time'}
            elif parser_type == "kaohsiung":
                if isinstance(json_data, dict): records = json_data.get('result', {}).get('records', [])
                key_map = {'car': 'CarNo', 'lat': 'Lat', 'lon': 'Lon', 'location': 'Location', 'time': 'Time'}
        except Exception as e:
            logger.error(f"Error while getting records for {city_name}: {e}")
            return []

        if not records: return []

        for truck in records:
            try:
                # 安全地取得所有資料，只要有一個欄位缺失或無法轉換，就跳過這筆
                car = truck.get(key_map['car'])
                lat = float(truck.get(key_map['lat']))
                lon = float(truck.get(key_map['lon']))
                location = truck.get(key_map['location'])
                time = truck.get(key_map['time'])

                if not all([car, location, time]): continue # lat/lon can be 0.0

                parsed_trucks.append({
                    'car': car, 'latitude': lat, 'longitude': lon,
                    'location': location, 'time': time, 'city': city_name
                })
            except (ValueError, TypeError, KeyError):
                continue # 任何解析或轉型錯誤都直接略過這筆不正確的資料
        return parsed_trucks

    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """(六都版) 查詢所有支援縣市的 API，並回傳指定範圍內的垃圾車"""
        all_nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        for city_code, api_info in CITY_APIS.items():
            try:
                # 檢查是否需要忽略 SSL 驗證 (針對桃園)
                verify_ssl = api_info.get("verify_ssl", True)
                response = requests.get(api_info['url'], timeout=20, verify=verify_ssl)
                response.raise_for_status() # 確保狀態碼是 200
                
                json_data = response.json()
                city_trucks = self._parse_data(json_data, api_info['parser'], api_info['name'])

                for truck in city_trucks:
                    dist_sq = ((truck['latitude'] - user_lat) * 111)**2 + ((truck['longitude'] - user_lon) * 111)**2
                    if dist_sq <= radius_km**2:
                        truck['distance'] = round(dist_sq**0.5, 2)
                        all_nearby_trucks.append(truck)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to connect or request from {api_info['name']} API: {e}")
            except ValueError as e: # 處理 JSON 解碼失敗
                 logger.error(f"Failed to decode JSON from {api_info['name']} API: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred for {api_info['name']}: {e}")
        
        all_nearby_trucks.sort(key=lambda x: x['distance'])
        logger.info(f"Found {len(all_nearby_trucks)} nearby garbage trucks from all supported cities.")
        return all_nearby_trucks
