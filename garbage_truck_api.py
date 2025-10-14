import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# --- 各縣市垃圾車公開資料 API 網址 ---
# 我們以新北市為範例，因為它的 API 格式最通用
# 資料來源：新北市政府資料開放平台
GARBAGE_TRUCK_API_URL = "https://data.ntpc.gov.tw/api/datasets/28AB4122-60E1-4065-98E5-AB48A68B3516/json?page=0&size=1000"

class GarbageTruckAPI:
    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 1.0) -> List[Dict]:
        """
        取得指定經緯度附近一定範圍內的垃圾車資訊 (以新北市為例)
        """
        nearby_trucks = []
        try:
            response = requests.get(GARBAGE_TRUCK_API_URL, timeout=10)
            # 檢查 API 是否成功回應
            if response.status_code != 200:
                logger.error(f"Failed to fetch garbage truck data. Status code: {response.status_code}")
                return []
            
            all_trucks = response.json()
            
            # 將使用者座標轉換為浮點數
            user_lat = float(latitude)
            user_lon = float(longitude)

            for truck in all_trucks:
                try:
                    truck_lat = float(truck.get('latitude'))
                    truck_lon = float(truck.get('longitude'))

                    # 使用簡易的歐幾里得距離平方來計算，避免開根號以提升效能
                    # 緯度一度約 111 公里
                    dist_sq = ((truck_lat - user_lat) * 111)**2 + ((truck_lon - user_lon) * 111)**2
                    
                    if dist_sq <= radius_km**2:
                        # 整理需要的資訊
                        truck_info = {
                            'car': truck.get('car'),
                            'location': truck.get('location'),
                            'time': truck.get('time'),
                            'distance': round(dist_sq**0.5, 2) # 開根號得到實際距離(公里)
                        }
                        nearby_trucks.append(truck_info)
                except (ValueError, TypeError):
                    # 如果經緯度資料有問題，跳過這筆
                    continue
            
            # 根據距離排序，最近的在最前面
            nearby_trucks.sort(key=lambda x: x['distance'])
            
            logger.info(f"Found {len(nearby_trucks)} nearby garbage trucks.")
            return nearby_trucks

        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to garbage truck API: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred in get_nearby_trucks: {e}")
            return []
