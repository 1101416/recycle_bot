import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 高雄市垃圾車「清運時間表」 API (官方文件確認) ---
KAOHSIUNG_SCHEDULE_API_URL = "https://api.kcg.gov.tw/api/service/Get/14fe516d-ac62-4905-9325-70daae7616bd"

class GarbageTruckAPI:
    def get_schedules_by_address(self, address: str) -> List[Dict]:
        """
        (終極耐心版) 根據使用者地址，查詢並匹配對應的清運點時間表
        """
        matching_schedules = []
        if not address:
            return []

        # 1. 從使用者地址中解析出「區」和「路/街」
        try:
            parts = address.replace("台灣", "").replace("臺灣", "").split('市')
            if len(parts) < 2: return []
            
            address_details = parts[1]
            district = address_details.split('區')[0] + '區'
            
            road = ""
            for keyword in ['路', '街', '大道', '巷']:
                if keyword in address_details:
                    road = address_details.split(keyword)[0].split('區')[-1] + keyword
                    break
            
            if not road:
                logger.warning(f"Could not parse road from address: {address}")
                # 即使沒有路，也繼續嘗試用行政區匹配
                road = "" 
        except Exception as e:
            logger.error(f"Error parsing address '{address}': {e}")
            return []

        logger.info(f"Parsed address: district='{district}', road='{road}'")

        # 2. 獲取全部的時間表資料
        try:
            # 模擬瀏覽器並將等待時間延長到極限的 60 秒
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(KAOHSIUNG_SCHEDULE_API_URL, timeout=60, headers=headers)
            response.raise_for_status()
            
            json_response = response.json()
            all_schedules = json_response.get("data", [])

            if not all_schedules:
                logger.warning("Kaohsiung API returned no data.")
                return []
        
        except requests.exceptions.Timeout:
            logger.error("Request to Kaohsiung API timed out even after 60 seconds. The server is confirmed to be unstable or offline.")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect or request from Kaohsiung API: {e}")
            return []
        except ValueError: # 包含 JSONDecodeError
            logger.error("Failed to decode JSON from Kaohsiung API. The API returned invalid data.")
            return []

        # 3. 篩選出符合「區」和「路/街」的清運點
        for point in all_schedules:
            try:
                point_area = point.get('area')
                point_caption = point.get('caption')

                if not point_area or not point_caption:
                    continue
                
                if point_area == district:
                    if road and road in point_caption:
                        schedule_info = {
                            'car': point.get('car_licence', '未知車號'),
                            'location': point_caption,
                            'time': f"{point.get('today_s', '')} - {point.get('today_e', '')}",
                            'city': '高雄市'
                        }
                        matching_schedules.append(schedule_info)
                    elif not road: # 如果地址無法解析出路名，回傳該行政區的所有清運點
                        schedule_info = {
                            'car': point.get('car_licence', '未知車號'),
                            'location': point_caption,
                            'time': f"{point.get('today_s', '')} - {point.get('today_e', '')}",
                            'city': '高雄市'
                        }
                        matching_schedules.append(schedule_info)
            except Exception:
                continue

        logger.info(f"Found {len(matching_schedules)} matching schedules for address: {address}")
        return matching_schedules
