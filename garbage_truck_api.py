import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 高雄市垃圾車即時 GPS 位置 API (最終驗證版) ---
KAOHSIUNG_REALTIME_API_URL = "https://data.kcg.gov.tw/api/action/datastore_search?resource_id=1999b828-a623-4c07-957e-39a7b94b42b1&limit=2000"

class GarbageTruckAPI:
    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """
        (高雄市專用版 v3) 專注於即時位置 API，並具備最強的錯誤處理能力
        """
        nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        try:
            # 延長等待時間至 30 秒，以應對政府伺服器緩慢的問題
            response = requests.get(KAOHSIUNG_REALTIME_API_URL, timeout=30)
            response.raise_for_status() # 確保狀態碼是 200

            json_data = response.json()
            # 這個 API 的資料包在 'result' -> 'records' 裡面
            all_trucks = json_data.get("result", {}).get("records", [])
            
            if not all_trucks or not isinstance(all_trucks, list):
                logger.warning("Kaohsiung real-time API returned no valid records.")
                return []

            for truck in all_trucks:
                try:
                    # 安全地解析即時 API 的資料欄位
                    car_no = truck.get('CarNo')
                    lat_str = truck.get('Lat')
                    lon_str = truck.get('Lon')
                    location = truck.get('Location')
                    time = truck.get('Time')

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
                
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Skipping a truck record due to parsing error: {e}. Record: {truck}")
                    continue
        
        except requests.exceptions.Timeout:
            logger.error(f"Request to Kaohsiung API timed out. The server is likely offline or under heavy load.")
            return [] # 超時也回傳空列表
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
