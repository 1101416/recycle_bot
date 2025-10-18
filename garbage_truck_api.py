import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 新北市垃圾車「即時位置」 API 網址 (正確版本) ---
NEW_TAIPEI_REALTIME_API_URL = "https://data.ntpc.gov.tw/api/datasets/28AB4122-60E1-4065-98E5-AB48A68B3516/json?page=0&size=2000"

class GarbageTruckAPI:
    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """
        (新北市專用版 v2) 查詢新北市「即時位置」API，並回傳指定範圍內的垃圾車
        """
        nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        try:
            response = requests.get(NEW_TAIPEI_REALTIME_API_URL, timeout=20)
            response.raise_for_status() # 確保狀態碼是 200

            # 這個 API 的回應就是一個 JSON 列表
            all_trucks = response.json()
            
            if not all_trucks or not isinstance(all_trucks, list):
                logger.warning("New Taipei real-time API returned no valid data.")
                return []

            for truck in all_trucks:
                try:
                    # 安全地解析「即時位置」API 的資料欄位
                    car_no = truck.get('car')
                    lat_str = truck.get('latitude')
                    lon_str = truck.get('longitude')
                    location = truck.get('location')
                    time = truck.get('time')

                    # 確保所有必要欄位都存在，特別是經緯度
                    if not all([car_no, location, time, lat_str, lon_str]):
                        continue
                    
                    lat = float(lat_str)
                    lon = float(lon_str)

                    # 計算距離
                    dist_sq = ((lat - user_lat) * 111)**2 + ((lon - user_lon) * 111)**2
                    if dist_sq <= radius_km**2:
                        truck_info = {
                            'car': car_no,
                            'location': location,
                            'time': time,
                            'city': '新北市',
                            'distance': round(dist_sq**0.5, 2)
                        }
                        nearby_trucks.append(truck_info)
                
                except (ValueError, TypeError, KeyError):
                    # 任何解析錯誤都直接略過這筆不正確的資料
                    continue
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect or request from New Taipei real-time API: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return []

        # 根據距離排序
        nearby_trucks.sort(key=lambda x: x['distance'])
        logger.info(f"Found {len(nearby_trucks)} nearby real-time garbage trucks in New Taipei City.")
        return nearby_trucks
