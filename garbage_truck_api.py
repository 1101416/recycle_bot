import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 高雄市垃圾車公開資料 API 網址 (根據官方文件) ---
KAOHSIUNG_API_URL = "https://api.kcg.gov.tw/api/service/Get/14fe516d-ac62-4905-9325-70daae7616bd"

class GarbageTruckAPI:
    def get_nearby_trucks(self, latitude: float, longitude: float, radius_km: float = 2.0) -> List[Dict]:
        """
        (高雄市專用版 v3) 根據官方文件重新實作，並具備最強的錯誤處理能力
        """
        nearby_trucks = []
        user_lat = float(latitude)
        user_lon = float(longitude)

        try:
            # 延長等待時間至 30 秒，這是應對政府伺服器緩慢的關鍵
            response = requests.get(KAOHSIUNG_API_URL, timeout=40)
            response.raise_for_status() # 確保狀態碼是 200

            json_response = response.json()
            # 根據官方文件，資料包在 'data' 這個 key 裡面
            all_trucks = json_response.get("data", [])
            
            if not all_trucks or not isinstance(all_trucks, list):
                logger.warning("Kaohsiung API returned no valid data in 'data' field.")
                return []

            for truck in all_trucks:
                try:
                    # 根據您提供的 API 格式，安全地解析「清運時間表」資料
                    area = truck.get('area')
                    location = truck.get('caption')
                    start_time = truck.get('today_s')
                    end_time = truck.get('today_e')
                    car_no = truck.get('car_licence')

                    # 確保所有必要欄位都存在
                    if not all([area, location, start_time, car_no]):
                        continue
                    
                    # 由於這是時間表 API，沒有經緯度，我們無法計算距離
                    # 我們改為回傳所有符合使用者所在行政區的清運點
                    # (這裡我們做一個簡化，直接回傳所有找到的清運點)
                    
                    schedule_info = {
                        'car': car_no,
                        'location': f"{area} - {location}",
                        'time': f"{start_time} - {end_time}",
                        'city': '高雄市',
                        'distance': 0 # 標示為 0，因為無法計算
                    }
                    nearby_trucks.append(schedule_info)
                
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Skipping a schedule record due to parsing error: {e}. Record: {truck}")
                    continue
        
        except requests.exceptions.Timeout:
            logger.error(f"Request to Kaohsiung API timed out. The server is likely offline or under heavy load.")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect or request from Kaohsiung API: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return []

        logger.info(f"Found {len(nearby_trucks)} schedules in Kaohsiung City.")
        # 我們不再按距離排序，因為沒有距離資訊
        return nearby_trucks
