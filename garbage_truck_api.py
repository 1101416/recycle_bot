import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 高雄市垃圾車公開資料 API 網址 (備用官方端點) ---
KAOHSIUNG_API_URL = "https://data.kcg.gov.tw/api/action/datastore_search?resource_id=1999b828-a623-4c07-957e-39a7b94b42b1&limit=2000"

class GarbageTruckAPI:
    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """
        (高雄市專用版 v2) 查詢高雄市備用 API，並回傳指定範圍內的垃圾車
        """
        nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        try:
            response = requests.get(KAOHSIUNG_API_URL, timeout=20)
            response.raise_for_status() # 確保狀態碼是 200

            # 這個備用 API 的資料包在 'result' -> 'records' 裡面
            json_data = response.json()
            all_trucks = json_data.get("result", {}).get("records", [])
            
            if not all_trucks or not isinstance(all_trucks, list):
                logger.warning("Kaohsiung backup API returned no valid records.")
                return []

            for truck in all_trucks:
                try:
                    # 安全地解析備用 API 的資料欄位
                    car_no = truck.get('CarNo')
                    lat_str = truck.get('Lat')
                    lon_str = truck.get('Lon')
                    location = truck.get('Location')
                    time = truck.get('Time')

                    # 確保經緯度存在且可轉換為數字
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
                            'city': '高雄市',
                            'distance': round(dist_sq**0.5, 2)
                        }
                        nearby_trucks.append(truck_info)
                
                except (ValueError, TypeError, KeyError):
                    continue
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect or request from Kaohsiung backup API: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return []

        # 根據距離排序
        nearby_trucks.sort(key=lambda x: x['distance'])
        logger.info(f"Found {len(nearby_trucks)} nearby garbage trucks in Kaohsiung City via backup API.")
        return nearby_trucks
