# garbage_truck_api.py
import requests
import logging
import math
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# 注意：使用可用（範例）URL（大小寫可能會影響某些伺服器）
KAOHSIUNG_SCHEDULE_API_URL = "https://api.kcg.gov.tw/Api/Service/Get/14fe516d-ac62-4905-9325-70daae7616bd"

# --- 小工具：距離 (Haversine) 回傳公尺 ---
def haversine_distance_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _extract_items_from_response(json_obj: Any) -> List[Dict]:
    """
    支援多種 API 回傳格式：{'data': [...]}, {'records': [...]}, {'value': [...]}, list, single dict
    若 json_obj 為 dict，會尋找常見包含 list 的欄位；最後 fallback 將 dict 包成 list 回傳。
    """
    if isinstance(json_obj, dict):
        for key in ("data", "Data", "records", "Records", "value", "Value", "results", "Results"):
            if key in json_obj and isinstance(json_obj[key], list):
                return json_obj[key]
        # 如果 dict 裡任何欄位是 list，就拿第一個 list
        for k, v in json_obj.items():
            if isinstance(v, list):
                return v
        # 否則把整個 dict 當作一筆 item
        return [json_obj]
    elif isinstance(json_obj, list):
        return json_obj
    else:
        return []

def _get_field_case_insensitive(obj: Dict, candidates: List[str], default=None):
    if not isinstance(obj, dict):
        return default
    # 先直接找 exact key
    for c in candidates:
        if c in obj:
            return obj[c]
    # 再用 lower-case 比對
    lower_map = {k.lower(): k for k in obj.keys()}
    for c in candidates:
        lc = c.lower()
        if lc in lower_map:
            return obj[lower_map[lc]]
    return default

class GarbageTruckAPI:
    def __init__(self, api_url: str = None):
        self.api_url = api_url or KAOHSIUNG_SCHEDULE_API_URL

    def get_schedules_by_address(self, address: str, radius_m: int = 2000) -> List[Dict]:
        """
        根據使用者地址（字串），查詢垃圾車清運時間表並以行政區/路段匹配。
        回傳 List[Dict]，每筆 dict 包含：'car','location','time','city'
        """
        if not address:
            return []

        # 解析行政區與路名（簡單 heuristics，保留原行為）
        try:
            parts = address.replace("台灣", "").replace("臺灣", "").split('市')
            if len(parts) < 2:
                # address 可能已經是 "高雄市三民區..." 或不含市字，嘗試找 "區"
                addr_after = address
            else:
                addr_after = parts[1]
            if '區' in addr_after:
                district = addr_after.split('區')[0] + '區'
            else:
                # fallback: 嘗試包含縣市+區，或整段當作搜尋字串
                district = ''
            road = ""
            for keyword in ['路', '街', '大道', '巷']:
                if keyword in addr_after:
                    # 取區後到該 keyword 的字串
                    try:
                        road = addr_after.split(keyword)[0].split('區')[-1] + keyword
                    except Exception:
                        road = ""
                    break
        except Exception as e:
            logger.exception(f"Address parsing failed for '{address}': {e}")
            district = ""
            road = ""

        logger.info(f"Parsed address -> district: '{district}', road: '{road}'")

        # 取得 API 資料
        headers = {
            'User-Agent': 'GreenLine/1.0 (https://github.com/your-repo)'
        }
        try:
            resp = requests.get(self.api_url, timeout=20, headers=headers)
            resp.raise_for_status()
            json_obj = resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch Kaohsiung schedule API: {e}")
            # 若失敗，記錄回傳內容(若有) 並回傳空清單
            try:
                logger.debug(f"API raw response text: {getattr(e.response, 'text', None)}")
            except Exception:
                pass
            return []
        except ValueError as e:
            logger.error(f"Invalid JSON from Kaohsiung API: {e}")
            logger.debug(f"Raw text: {resp.text[:2000] if 'resp' in locals() else 'no resp'}")
            return []

        items = _extract_items_from_response(json_obj)
        if not items:
            logger.warning("Kaohsiung API returned no usable items.")
            logger.debug(f"Full JSON: {json_obj}")
            return []

        matching_schedules = []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                # 取得 area / caption / 車號 / 時間欄位（大小寫不敏感）
                point_area = _get_field_case_insensitive(it, ['area', 'Area', 'AREA', '行政區', '區域'], default=None)
                point_caption = _get_field_case_insensitive(it, ['caption', 'Caption', '名稱', 'Name', 'location', 'Location', 'LOCATION'], default=None)

                # 若有 geometry 座標可進一步處理 (非必要)
                # 嘗試取得時間 start/end 或預估時間欄位
                today_s = _get_field_case_insensitive(it, ['today_s', 'Today_s', 'start_time', 'StartTime', 'todayStart'], default=None)
                today_e = _get_field_case_insensitive(it, ['today_e', 'Today_e', 'end_time', 'EndTime', 'todayEnd'], default=None)
                if not today_s and not today_e:
                    # 也可能存在單一欄位 "time" 或 "Time"
                    t_single = _get_field_case_insensitive(it, ['time', 'Time', '預計時間', 'time_text'], default=None)
                    if t_single:
                        today_s = t_single
                        today_e = ""

                car_license = _get_field_case_insensitive(it, ['car_licence', 'carLicence', 'carNo', 'car', '車號'], default='未知車號')

                # 判斷行政區/路段是否匹配（容錯：如果 API area 含「高雄市三民區」，就用包含比對）
                area_ok = False
                if district:
                    if point_area and district in str(point_area):
                        area_ok = True
                else:
                    # 若沒抓到 district，就 accept all（交由路名或 caption 篩選）
                    area_ok = True

                road_ok = False
                if road:
                    if point_caption and road in str(point_caption):
                        road_ok = True
                else:
                    road_ok = True

                if area_ok and road_ok:
                    schedule_info = {
                        'car': car_license,
                        'location': str(point_caption) if point_caption else str(_get_field_case_insensitive(it, ['address', 'Address', 'addr'], default='未知地點')),
                        'time': f"{today_s or ''}{(' - ' + today_e) if today_e else ''}".strip(),
                        'city': '高雄市'
                    }
                    matching_schedules.append(schedule_info)
            except Exception:
                # 個別 item 解析錯誤不影響整體
                logger.debug(f"Failed to parse item: {it}", exc_info=True)
                continue

        logger.info(f"Found {len(matching_schedules)} matching schedules for address '{address}'")
        return matching_schedules
