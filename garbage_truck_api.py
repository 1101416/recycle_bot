import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 桃園市垃圾車即時動態 API (網站背後的隱藏版 API) ---
# 這個 API 會回傳桃園市所有正在線上作業的垃圾車即時資訊
TAOYUAN_REALTIME_API_URL = "https://route.tyoem.gov.tw/api/get_all_car_location"

class GarbageTruckAPI:
    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """
        (桃園市專用版 v2) 透過爬取網站背後的 API 來取得即時垃圾車資訊
        """
        nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        try:
            # 這個網站的 API 不需要 SSL 驗證，直接呼叫即可
            response = requests.get(TAOYUAN_REALTIME_API_URL, timeout=20)
            response.raise_for_status() # 確保狀態碼是 200

            # API 回傳的資料格式是一個 list of dictionaries
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
                    
                    # 網站 API 沒有提供 "location" 和 "time"，我們先給予預設值
                    location = truck.get('address', '即時位置更新') # 嘗試取得地址，若無則給預設
                    time = truck.get('update_time', '') # 取得更新時間

                    if not all([car_no, lat, lon]):
                        continue

                    # 計算距離
                    dist_sq = ((lat - user_lat) * 111)**2 + ((lon - user_lon) * 111)**2
                    if dist_sq <= radius_km**2:
                        truck_info = {
                            'car': car_no,
                            'location': location,
                            'time': time.split(' ')[-1], # 只取時間部分
                            'city': '桃園市',
                            'distance': round(dist_sq**0.5, 2)
                        }
                        nearby_trucks.append(truck_info)
                
                except (ValueError, TypeError, KeyError):
                    # 任何解析錯誤都直接略過這筆不正確的資料
                    continue
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect or request from Taoyuan real-time API: {e}")
            return [] # 發生連線錯誤時回傳空列表
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return []

        # 根據距離排序
        nearby_trucks.sort(key=lambda x: x['distance'])
        logger.info(f"Found {len(nearby_trucks)} nearby garbage trucks in Taoyuan via web API.")
        return nearby_trucks
