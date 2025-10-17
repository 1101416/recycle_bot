import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 高雄市垃圾車「清運時間表」 API ---
KAOHSIUNG_SCHEDULE_API_URL = "https://api.kcg.gov.tw/api/service/Get/14fe516d-ac62-4905-9325-70daae7616bd"

class GarbageTruckAPI:
    def get_schedules_by_address(self, address: str) -> List[Dict]:
        """
        (智慧時間表版) 根據使用者地址，查詢並匹配對應的清運點時間表
        """
        nearby_schedules = []
        if not address:
            return []

        try:
            # 1. 從使用者地址中解析出「區」和「路/街」
            # 簡單的解析，例如 "高雄市仁武區八德西路..." -> "仁武區", "八德西路"
            parts = address.replace("台灣", "").replace("臺灣", "").split('市')
            if len(parts) < 2:
                return [] # 無法解析出區
            
            address_details = parts[1]
            district = address_details.split('區')[0] + '區'
            
            # 尋找路、街、大道等關鍵字
            road = ""
            for keyword in ['路', '街', '大道']:
                if keyword in address_details:
                    # 抓取到 keyword 為止的部分
                    road = address_details.split(keyword)[0].split('區')[-1] + keyword
                    break
            
            if not road:
                logger.warning(f"Could not parse road from address: {address}")
                return []

            logger.info(f"Parsed address: district='{district}', road='{road}'")

            # 2. 獲取全部的時間表資料
            response = requests.get(KAOHSIUNG_SCHEDULE_API_URL, timeout=30)
            response.raise_for_status()
            all_schedules = response.json().get("data", [])

            if not all_schedules:
                return []

            # 3. 篩選出符合「區」和「路/街」的清運點
            for point in all_schedules:
                # 確保資料齊全
                if not all(k in point for k in ['area', 'caption', 'today_s']):
                    continue
                
                # 進行匹配
                if point['area'] == district and road in point['caption']:
                    schedule_info = {
                        'car': point.get('car_licence', '未知車號'),
                        'location': point.get('caption', '未知地點'),
                        'time': f"{point.get('today_s', '')} - {point.get('today_e', '')}",
                        'city': '高雄市'
                    }
                    nearby_schedules.append(schedule_info)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Kaohsiung Schedule API: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred in get_schedules_by_address: {e}")
            return []

        logger.info(f"Found {len(nearby_schedules)} matching schedules for address: {address}")
        return nearby_schedules
