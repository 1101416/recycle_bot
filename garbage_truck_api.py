import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 高雄市垃圾車公開資料 API 網址 ---
# 資料來源：高雄市政府資料開放平台
KAOHSIUNG_API_URL = "https://api.kcg.gov.tw/api/service/Get/14fe516d-ac62-4905-9325-70daae7616bd"

class GarbageTruckAPI:
    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """
        (高雄市專用版) 查詢高雄市 API，並回傳指定範圍內的垃圾車
        """
        nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        try:
            response = requests.get(KAOHSIUNG_API_URL, timeout=20)
            response.raise_for_status() # 確保狀態碼是 200

            # 高雄市 API 的資料包在 'data' 這個 key 裡面
            all_trucks = response.json().get("data", [])
            
            if not all_trucks or not isinstance(all_trucks, list):
                logger.warning("Kaohsiung API returned no valid data in 'data' field.")
                return []

            for truck in all_trucks:
                try:
                    # 安全地解析高雄市 API 的資料欄位
                    car_no = truck.get('car_no')
                    lat = float(truck.get('car_lat'))
                    lon = float(truck.get('car_lon'))
                    location = truck.get('location')
                    time = truck.get('work_time') # 高雄 API 使用 work_time

                    if not all([car_no, location, time, lat is not None, lon is not None]):
                        continue

                    # 計算距離
                    dist_sq = ((lat - user_lat) * 111)**2 + ((lon - user_lon) * 111)**2
                    if dist_sq <= radius_km**2:
                        truck_info = {
                            'car': car_no,
                            'location': location,
                            'time': time,
                            'city': '高雄市', # 直接標示為高雄市
                            'distance': round(dist_sq**0.5, 2)
                        }
                        nearby_trucks.append(truck_info)
                
                except (ValueError, TypeError, KeyError):
                    # 任何解析錯誤都直接略過這筆不正確的資料
                    continue
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect or request from Kaohsiung API: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return []

        # 根據距離排序
        nearby_trucks.sort(key=lambda x: x['distance'])
        logger.info(f"Found {len(nearby_trucks)} nearby garbage trucks in Kaohsiung City.")
        return nearby_trucks
