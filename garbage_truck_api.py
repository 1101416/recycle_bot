import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# --- 多縣市垃圾車公開資料 API 網址庫 ---
CITY_APIS = {
    "taipei": {
        "name": "臺北市",
        "url": "https://data.taipei/api/v1/dataset/a8025D87-2D99-43C6-9E2A-78E56839352F?scope=resourceAquire",
        "parser": "taipei" # 指定使用台北市的解析格式
    },
    "new_taipei": {
        "name": "新北市",
        "url": "https://data.ntpc.gov.tw/api/datasets/28AB4122-60E1-4065-98E5-AB48A68B3516/json?page=0&size=1000",
        "parser": "new_taipei" # 指定使用新北市的解析格式
    },
    "taoyuan": {
        "name": "桃園市",
        "url": "https://data.tycg.gov.tw/api/v1/rest/datastore/a1b4714b-fc25-4671-a533-606540c55768?limit=1000",
        "parser": "taoyuan" # 指定使用桃園市的解析格式
    },
    "taichung": {
        "name": "臺中市",
        "url": "https://datacenter.taichung.gov.tw/swagger/OpenData/9188423a-1336-4b13-8822-ea1391b03361",
        "parser": "taichung" # 指定使用台中市的解析格式
    }
}

class GarbageTruckAPI:

    def _parse_data(self, json_data: List[Dict], parser_type: str, city_name: str) -> List[Dict]:
        """根據不同縣市的 API 格式，解析並標準化垃圾車資料"""
        parsed_trucks = []
        
        # 根據 parser_type 選擇對應的欄位名稱
        key_map = {}
        if parser_type == "taipei":
            key_map = {'car': 'car', 'lat': 'lat', 'lon': 'lon', 'location': 'location', 'time': 'time'}
            records = json_data.get('result', {}).get('records', [])
        elif parser_type == "new_taipei":
            key_map = {'car': 'car', 'lat': 'latitude', 'lon': 'longitude', 'location': 'location', 'time': 'time'}
            records = json_data
        elif parser_type == "taoyuan":
            key_map = {'car': 'Car', 'lat': 'Lat', 'lon': 'Lon', 'location': 'Location', 'time': 'Time'}
            records = json_data.get('result', {}).get('records', [])
        elif parser_type == "taichung":
            key_map = {'car': 'car_id', 'lat': 'lat', 'lon': 'lng', 'location': 'location', 'time': 'time'}
            records = json_data
        else:
            return []

        for truck in records:
            try:
                # 確保所有必要的欄位都存在且非空
                if all(truck.get(key) for key in key_map.values()):
                    parsed_trucks.append({
                        'car': truck[key_map['car']],
                        'latitude': float(truck[key_map['lat']]),
                        'longitude': float(truck[key_map['lon']]),
                        'location': truck[key_map['location']],
                        'time': truck[key_map['time']],
                        'city': city_name
                    })
            except (ValueError, TypeError, KeyError):
                continue
        return parsed_trucks

    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """
        (多縣市版) 查詢所有支援縣市的 API，並回傳指定範圍內的垃圾車
        """
        all_nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        # 遍歷所有城市的 API
        for city_code, api_info in CITY_APIS.items():
            try:
                response = requests.get(api_info['url'], timeout=15)
                if response.status_code != 200:
                    logger.warning(f"API for {api_info['name']} failed with status {response.status_code}.")
                    continue
                
                # 解析該城市的資料
                city_trucks = self._parse_data(response.json(), api_info['parser'], api_info['name'])

                for truck in city_trucks:
                    # 計算距離
                    dist_sq = ((truck['latitude'] - user_lat) * 111)**2 + ((truck['longitude'] - user_lon) * 111)**2
                    if dist_sq <= radius_km**2:
                        truck['distance'] = round(dist_sq**0.5, 2)
                        all_nearby_trucks.append(truck)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Error connecting to {api_info['name']} API: {e}")
                continue # 一個城市失敗，繼續嘗試下一個
        
        # 根據距離排序，最近的在最前面
        all_nearby_trucks.sort(key=lambda x: x['distance'])
        
        logger.info(f"Found {len(all_nearby_trucks)} nearby garbage trucks from all cities.")
        return all_nearby_trucks
