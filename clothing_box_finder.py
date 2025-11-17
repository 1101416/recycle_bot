
import csv
import logging
import math
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)

# 舊衣回收箱 CSV 檔案的路徑 (請確保檔案名稱與您上傳的一致)
OLD_CLOTHES_CSV_PATH = 'old_clothes_WITH_COORDS_full.csv'

# (這個函式是從 garbage_truck_api.py 複製過來的，用於計算距離)
def haversine_distance_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class ClothingBoxFinder:
    def __init__(self, csv_path=OLD_CLOTHES_CSV_PATH):
        self.csv_path = csv_path
        self.all_boxes_data = []
        self._load_data()

    def _load_data(self):
        """
        在啟動時，將 CSV 資料讀取到記憶體中。
        """
        try:
            # 使用 'utf-8-sig' 來處理可能存在的 BOM (位元組順序記號)
            with open(self.csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    # 確保經緯度欄位存在且是有效數字
                    try:
                        lat = float(row.get('latitude'))
                        lon = float(row.get('longitude'))
                        
                        self.all_boxes_data.append({
                            "name": row.get('name', '未命名地點'),
                            "address": row.get('address', '地址未提供'),
                            "latitude": lat,
                            "longitude": lon
                        })
                        count += 1
                    except (ValueError, TypeError):
                        # 如果經緯度為空或格式錯誤，則跳過該筆資料
                        logger.warning(f"Skipping clothing box row due to invalid coords: {row.get('name')}")
                        continue
            logger.info(f"Loaded {count} clothing box locations from CSV.")
        except FileNotFoundError:
            logger.error(f"CRITICAL: Clothing box CSV file not found at {self.csv_path}")
        except Exception as e:
            logger.error(f"Error loading clothing box CSV: {e}")

    def get_nearby_boxes(self, lat: float, lng: float, radius_m: int = 2000, max_results: int = 3) -> List[Dict]:
        """
        以經緯度計算距離，並回傳最近的 X 筆結果。
        """
        if not self.all_boxes_data:
            logger.warning("No clothing box data loaded, cannot perform search.")
            return []

        proximity_results = []
        for box in self.all_boxes_data:
            try:
                d = haversine_distance_m(lat, lng, box['latitude'], box['longitude'])
                if d <= radius_m:
                    res = {
                        "name": box['name'],
                        "address": box['address'],
                        "_distance_m": int(d)
                    }
                    proximity_results.append(res)
            except Exception:
                logger.exception(f"Distance calc failed for clothing box: {box.get('name')}")
                continue

        if proximity_results:
            # 依照距離排序
            proximity_results.sort(key=lambda x: x["_distance_m"])
            logger.info(f"Found {len(proximity_results)} clothing boxes within {radius_m}m, returning top {max_results}.")
            # 回傳前 max_results 筆
            return proximity_results[:max_results]
        
        logger.info(f"No clothing boxes found within {radius_m}m.")
        return []
