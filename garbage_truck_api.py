import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 桃園市垃圾車即時動態 API (最終驗證版) ---
TAOYUAN_REALTIME_API_URL = "https://route.tyoem.gov.tw/api/get_all_car_location"

class GarbageTruckAPI:
    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """
        (桃園市專用版 v4) 透過爬取網站背後的 API (並加上 Referer) 來取得即時垃圾車資訊
        """
        nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        try:
            # V V V 這是本次修正的關鍵 V V V
            # 模擬瀏覽器發出請求，加上 Referer "通行證"
            headers = {
                'Referer': 'https://route.tyoem.gov.tw/'
            }
            # ^ ^ ^ 這是本次修正的關鍵 ^ ^ ^

            response = requests.get(TAOYUAN_REALTIME_API_URL, headers=headers, timeout=20)
            response.raise_for_status() # 確保狀態碼是 200

            all_trucks = response.json()
            
            if not all_trucks or not isinstance(all_trucks, list):
                logger.warning("Taoyuan real-time API returned no valid data.")
                return []

            for truck in all_trucks:
                try:
                    # 安全地解析資料
                    car_no = truck.get('car_no')
                    lat = float(truck.get('lat'))
                    lon = float(truck.get('lon'))
                    location = truck.get('address', '即時位置更新')
                    time = truck.get('update_time', '').split(' ')[-1] # 只取時間部分

                    if not all([car_no, lat, lon]):
                        continue

                    # 計算距離
                    dist_sq = ((lat - user_lat) * 111)**2 + ((lon - user_lon) * 111)**2
                    if dist_sq <= radius_km**2:
                        truck_info = {
                            'car': car_no,
                            'location': location,
                            'time': time,
                            'city': '桃園市',
                            'distance': round(dist_sq**0.5, 2)
                        }
                        nearby_trucks.append(truck_info)
                
                except (ValueError, TypeError, KeyError):
                    continue
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect or request from Taoyuan real-time API: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return []

        # 根據距離排序
        nearby_trucks.sort(key=lambda x: x['distance'])
        logger.info(f"Found {len(nearby_trucks)} nearby garbage trucks in Taoyuan via web API.")
        return nearby_trucks
