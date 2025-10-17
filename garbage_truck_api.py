import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 桃園市垃圾車即時動態 API (2025年最新驗證版) ---
# 這是從官方 App "桃園環保通" 分析出的最新 API 端點
TAOYUAN_REALTIME_API_URL = "https://car.tyemid.gov.tw/api/car/positions"

class GarbageTruckAPI:
    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """
        (桃園市專用版 v3) 透過最新的官方 App API 來取得即時垃圾車資訊
        """
        nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        try:
            # 這個 API 需要一個固定的 Headers 才能正確回傳資料
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(TAOYUAN_REALTIME_API_URL, headers=headers, timeout=20)
            response.raise_for_status() # 確保狀態碼是 200

            # API 回傳的資料在 'Data' 這個 key 裡面
            all_trucks = response.json().get("Data", [])
            
            if not all_trucks or not isinstance(all_trucks, list):
                logger.warning("Taoyuan real-time API returned no valid data in 'Data' field.")
                return []

            for truck in all_trucks:
                try:
                    # 安全地解析新版 API 的資料欄位
                    car_no = truck.get('CarNo')
                    lat = float(truck.get('Lat'))
                    lon = float(truck.get('Lon'))
                    
                    # 新版 API 直接提供了地址和時間
                    location = truck.get('Address', '即時位置更新')
                    time = truck.get('GpsTime', '').split(' ')[-1] # 只取 HH:MM:SS

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
        logger.info(f"Found {len(nearby_trucks)} nearby garbage trucks in Taoyuan via latest web API.")
        return nearby_trucks
