import os
import requests
import time
import json
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import cv2
import numpy as np
from PIL import Image
import argparse
from typing import List, Dict, Optional
from config import Config

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WasteImageCollector:
    def __init__(self, output_dir='data/collected', max_images_per_category=1000):
        self.output_dir = output_dir
        self.max_images_per_category = max_images_per_category
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 建立輸出目錄
        os.makedirs(output_dir, exist_ok=True)
        
        # 垃圾分類搜尋關鍵字
        self.search_keywords = {
            'plastic': [
                '塑膠瓶', '塑膠容器', '塑膠袋', '保麗龍', '塑膠杯',
                'plastic bottle', 'plastic container', 'plastic bag', 'styrofoam',
                'プラスチックボトル', 'プラスチック容器', 'プラスチック袋',
                '플라스틱병', '플라스틱용기', '플라스틱봉지'
            ],
            'paper': [
                '報紙', '紙箱', '紙杯', '雜誌', '紙袋',
                'newspaper', 'cardboard', 'paper cup', 'magazine', 'paper bag',
                '新聞紙', '段ボール', '紙コップ', '雑誌', '紙袋',
                '신문지', '판지', '종이컵', '잡지', '종이봉지'
            ],
            'metal': [
                '鋁罐', '鐵罐', '鋁箔包', '金屬容器',
                'aluminum can', 'tin can', 'metal container',
                'アルミ缶', 'スチール缶', '金属容器',
                '알루미늄캔', '철캔', '금속용기'
            ],
            'glass': [
                '玻璃瓶', '玻璃容器', '酒瓶',
                'glass bottle', 'glass container', 'wine bottle',
                'ガラス瓶', 'ガラス容器', 'ワインボトル',
                '유리병', '유리용기', '와인병'
            ],
            'organic': [
                '果皮', '剩菜', '廚餘', '茶葉渣',
                'fruit peel', 'food waste', 'kitchen waste', 'tea leaves',
                '果物の皮', '生ゴミ', '茶殻',
                '과일껍질', '음식물쓰레기', '찻잎'
            ],
            'battery': [
                '電池', '乾電池', '鋰電池',
                'battery', 'dry battery', 'lithium battery',
                '電池', '乾電池', 'リチウム電池',
                '배터리', '건전지', '리튬배터리'
            ],
            'electronics': [
                '手機', '電腦', '家電', '電子產品',
                'mobile phone', 'computer', 'appliance', 'electronics',
                '携帯電話', 'コンピューター', '家電', '電子機器',
                '휴대폰', '컴퓨터', '가전제품', '전자제품'
            ],
            'other': [
                '衣物', '鞋子', '玩具', '其他',
                'clothes', 'shoes', 'toys', 'other',
                '衣類', '靴', 'おもちゃ', 'その他',
                '의류', '신발', '장난감', '기타'
            ]
        }
    
    def download_image(self, url: str, filename: str) -> bool:
        """下載圖片"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # 檢查內容類型
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                return False
            
            # 儲存圖片
            with open(filename, 'wb') as f:
                f.write(response.content)
            
            # 驗證圖片
            try:
                with Image.open(filename) as img:
                    img.verify()
                return True
            except Exception:
                os.remove(filename)
                return False
                
        except Exception as e:
            logger.warning(f"下載圖片失敗 {url}: {str(e)}")
            return False
    
    def search_google_images(self, query: str, max_images: int = 100) -> List[str]:
        """搜尋 Google 圖片"""
        image_urls = []
        
        try:
            # 使用 Google 圖片搜尋
            search_url = f"https://www.google.com/search?q={query}&tbm=isch"
            response = self.session.get(search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 尋找圖片 URL
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and src.startswith('http'):
                    image_urls.append(src)
                    if len(image_urls) >= max_images:
                        break
            
            logger.info(f"找到 {len(image_urls)} 張圖片: {query}")
            
        except Exception as e:
            logger.error(f"搜尋 Google 圖片失敗: {str(e)}")
        
        return image_urls
    
    def search_unsplash(self, query: str, max_images: int = 100) -> List[str]:
        """搜尋 Unsplash 圖片"""
        image_urls = []
        
        try:
            # Unsplash API (需要 API key)
            api_key = os.getenv('UNSPLASH_API_KEY')
            if not api_key:
                logger.warning("未設定 UNSPLASH_API_KEY，跳過 Unsplash 搜尋")
                return image_urls
            
            url = f"https://api.unsplash.com/search/photos"
            params = {
                'query': query,
                'per_page': min(max_images, 30),  # Unsplash 限制
                'client_id': api_key
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            for photo in data.get('results', []):
                image_urls.append(photo['urls']['regular'])
            
            logger.info(f"從 Unsplash 找到 {len(image_urls)} 張圖片: {query}")
            
        except Exception as e:
            logger.error(f"搜尋 Unsplash 圖片失敗: {str(e)}")
        
        return image_urls
    
    def search_pixabay(self, query: str, max_images: int = 100) -> List[str]:
        """搜尋 Pixabay 圖片"""
        image_urls = []
        
        try:
            # Pixabay API (需要 API key)
            api_key = os.getenv('PIXABAY_API_KEY')
            if not api_key:
                logger.warning("未設定 PIXABAY_API_KEY，跳過 Pixabay 搜尋")
                return image_urls
            
            url = "https://pixabay.com/api/"
            params = {
                'key': api_key,
                'q': query,
                'image_type': 'photo',
                'per_page': min(max_images, 200),  # Pixabay 限制
                'safesearch': 'true'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            for hit in data.get('hits', []):
                image_urls.append(hit['webformatURL'])
            
            logger.info(f"從 Pixabay 找到 {len(image_urls)} 張圖片: {query}")
            
        except Exception as e:
            logger.error(f"搜尋 Pixabay 圖片失敗: {str(e)}")
        
        return image_urls
    
    def collect_images_for_category(self, category: str, keywords: List[str]) -> int:
        """為特定類別收集圖片"""
        category_dir = os.path.join(self.output_dir, category)
        os.makedirs(category_dir, exist_ok=True)
        
        # 檢查現有圖片數量
        existing_images = len([f for f in os.listdir(category_dir) 
                              if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        
        if existing_images >= self.max_images_per_category:
            logger.info(f"{category} 類別已有足夠圖片 ({existing_images} 張)")
            return existing_images
        
        target_count = self.max_images_per_category - existing_images
        collected_count = 0
        
        logger.info(f"開始收集 {category} 類別圖片，目標: {target_count} 張")
        
        for keyword in keywords:
            if collected_count >= target_count:
                break
            
            logger.info(f"搜尋關鍵字: {keyword}")
            
            # 從不同來源搜尋圖片
            all_urls = []
            
            # Google 圖片搜尋
            google_urls = self.search_google_images(keyword, 50)
            all_urls.extend(google_urls)
            
            # Unsplash
            unsplash_urls = self.search_unsplash(keyword, 30)
            all_urls.extend(unsplash_urls)
            
            # Pixabay
            pixabay_urls = self.search_pixabay(keyword, 30)
            all_urls.extend(pixabay_urls)
            
            # 去重
            unique_urls = list(set(all_urls))
            
            # 下載圖片
            for i, url in enumerate(unique_urls):
                if collected_count >= target_count:
                    break
                
                filename = os.path.join(category_dir, f"{category}_{keyword}_{i:04d}.jpg")
                
                if self.download_image(url, filename):
                    collected_count += 1
                    logger.info(f"下載成功: {filename} ({collected_count}/{target_count})")
                
                # 避免請求過於頻繁
                time.sleep(0.5)
        
        logger.info(f"{category} 類別收集完成，共 {collected_count} 張圖片")
        return collected_count
    
    def collect_all_categories(self) -> Dict[str, int]:
        """收集所有類別的圖片"""
        results = {}
        
        for category, keywords in self.search_keywords.items():
            try:
                count = self.collect_images_for_category(category, keywords)
                results[category] = count
                
                # 類別間暫停
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"收集 {category} 類別圖片時發生錯誤: {str(e)}")
                results[category] = 0
        
        return results
    
    def validate_images(self, category: str) -> Dict[str, int]:
        """驗證和清理圖片"""
        category_dir = os.path.join(self.output_dir, category)
        
        if not os.path.exists(category_dir):
            return {'valid': 0, 'invalid': 0, 'removed': 0}
        
        valid_count = 0
        invalid_count = 0
        removed_count = 0
        
        for filename in os.listdir(category_dir):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            filepath = os.path.join(category_dir, filename)
            
            try:
                # 使用 PIL 驗證圖片
                with Image.open(filepath) as img:
                    img.verify()
                
                # 檢查圖片大小
                img = Image.open(filepath)
                if img.size[0] < 100 or img.size[1] < 100:
                    os.remove(filepath)
                    removed_count += 1
                    logger.warning(f"移除過小圖片: {filename}")
                else:
                    valid_count += 1
                    
            except Exception as e:
                # 移除無效圖片
                os.remove(filepath)
                invalid_count += 1
                logger.warning(f"移除無效圖片: {filename} - {str(e)}")
        
        logger.info(f"{category} 類別驗證完成: 有效 {valid_count}, 無效 {invalid_count}, 移除 {removed_count}")
        
        return {
            'valid': valid_count,
            'invalid': invalid_count,
            'removed': removed_count
        }
    
    def resize_images(self, category: str, target_size: tuple = (224, 224)) -> int:
        """調整圖片大小"""
        category_dir = os.path.join(self.output_dir, category)
        
        if not os.path.exists(category_dir):
            return 0
        
        resized_count = 0
        
        for filename in os.listdir(category_dir):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            filepath = os.path.join(category_dir, filename)
            
            try:
                with Image.open(filepath) as img:
                    # 調整大小並保持比例
                    img.thumbnail(target_size, Image.Resampling.LANCZOS)
                    
                    # 創建正方形圖片
                    new_img = Image.new('RGB', target_size, (255, 255, 255))
                    new_img.paste(img, ((target_size[0] - img.size[0]) // 2,
                                      (target_size[1] - img.size[1]) // 2))
                    
                    # 儲存
                    new_img.save(filepath, 'JPEG', quality=95)
                    resized_count += 1
                    
            except Exception as e:
                logger.warning(f"調整圖片大小失敗: {filename} - {str(e)}")
        
        logger.info(f"{category} 類別調整大小完成: {resized_count} 張")
        return resized_count
    
    def create_dataset_info(self) -> Dict:
        """創建資料集資訊"""
        dataset_info = {
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'categories': {},
            'total_images': 0,
            'image_size': Config.IMAGE_SIZE,
            'class_names': list(Config.WASTE_CATEGORIES.keys())
        }
        
        for category in self.search_keywords.keys():
            category_dir = os.path.join(self.output_dir, category)
            
            if os.path.exists(category_dir):
                image_count = len([f for f in os.listdir(category_dir) 
                                  if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                dataset_info['categories'][category] = image_count
                dataset_info['total_images'] += image_count
        
        # 儲存資訊
        info_path = os.path.join(self.output_dir, 'dataset_info.json')
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"資料集資訊已儲存: {info_path}")
        return dataset_info

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='垃圾分類圖片收集工具')
    parser.add_argument('--output_dir', default='data/collected', help='輸出目錄')
    parser.add_argument('--max_images', type=int, default=1000, help='每類別最大圖片數')
    parser.add_argument('--category', help='指定類別 (不指定則收集所有類別)')
    parser.add_argument('--validate', action='store_true', help='驗證圖片')
    parser.add_argument('--resize', action='store_true', help='調整圖片大小')
    parser.add_argument('--info', action='store_true', help='顯示資料集資訊')
    
    args = parser.parse_args()
    
    collector = WasteImageCollector(args.output_dir, args.max_images)
    
    if args.info:
        info = collector.create_dataset_info()
        print(f"資料集總計: {info['total_images']} 張圖片")
        for category, count in info['categories'].items():
            print(f"  {category}: {count} 張")
        return
    
    if args.category:
        if args.category not in collector.search_keywords:
            logger.error(f"未知類別: {args.category}")
            return
        
        keywords = collector.search_keywords[args.category]
        collector.collect_images_for_category(args.category, keywords)
    else:
        collector.collect_all_categories()
    
    if args.validate:
        for category in collector.search_keywords.keys():
            collector.validate_images(category)
    
    if args.resize:
        for category in collector.search_keywords.keys():
            collector.resize_images(category)
    
    # 創建資料集資訊
    collector.create_dataset_info()

if __name__ == '__main__':
    main()
