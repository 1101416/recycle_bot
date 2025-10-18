import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# --- 高雄市垃圾車「清運時間表」 API ---
KAOHSIUNG_SCHEDULE_API_URL = "https://api.kcg.gov.tw/api/service/Get/14fe516d-ac62-4905-9325-70daae7616bd"

class GarbageTruckAPI:
    def _fetch_api_data(self) -> List[Dict]:
        """
        (強固版) 呼叫 API 並安全地解析回傳的 JSON，提取出清單。
        融合了您提供的 kcg_truck_example.py 中的 extract_items 智慧。
        """
        try:
            # 延長等待時間至 30 秒，並加上 User-Agent 模擬瀏覽器
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(KAOHSIUNG_SCHEDULE_API_URL, timeout=30, headers=headers)
            response.raise_for_status()
            
            data = response.json()

            # 智慧地從回傳的 JSON 中找出清單資料
            if isinstance(data, dict):
                for key in ("data", "records", "value", "result"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
            elif isinstance(data, list):
                return data
            
            logger.warning("Kaohsiung API response format is unexpected, no list found.")
            return []
        
        except requests.exceptions.Timeout:
            logger.error("Request to Kaohsiung API timed out. The server is likely offline or under heavy load.")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect or request from Kaohsiung API: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching API data: {e}")
            return []

    def get_schedules_by_address(self, address: str) -> List[Dict]:
        """
        (地址匹配版) 根據使用者地址，查詢並匹配對應的清運點時間表
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
                return []
        except Exception as e:
            logger.error(f"Error parsing address '{address}': {e}")
            return []

        logger.info(f"Parsed address: district='{district}', road='{road}'")

        # 2. 獲取全部的時間表資料
        all_schedules = self._fetch_api_data()
        if not all_schedules:
            return []

        # 3. 篩選出符合「區」和「路/街」的清運點
        for point in all_schedules:
            try:
                point_area = point.get('area')
                point_caption = point.get('caption')

                if not point_area or not point_caption:
                    continue
                
                # 進行匹配：行政區必須完全符合，且路名必須出現在停靠點描述中
                if point_area == district and road in point_caption:
                    schedule_info = {
                        'car': point.get('car_licence', '未知車號'),
                        'location': point_caption,
                        'time': f"{point.get('today_s', '')} - {point.get('today_e', '')}",
                        'city': '高雄市'
                    }
                    matching_schedules.append(schedule_info)
            except Exception:
                continue # 忽略格式不符的單筆資料

        logger.info(f"Found {len(matching_schedules)} matching schedules for address: {address}")
        return matching_schedules
