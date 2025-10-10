import requests
import json
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)

class NewsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 環保相關新聞來源
        self.news_sources = {
            'zh-TW': [
                {
                    'name': '環保署新聞',
                    'url': 'https://www.epa.gov.tw/News.aspx',
                    'type': 'epa'
                },
                {
                    'name': '環境資訊中心',
                    'url': 'https://e-info.org.tw/',
                    'type': 'einfo'
                },
                {
                    'name': '綠色和平',
                    'url': 'https://www.greenpeace.org/taiwan/',
                    'type': 'greenpeace'
                }
            ],
            'en': [
                {
                    'name': 'Environmental News Network',
                    'url': 'https://www.enn.com/',
                    'type': 'enn'
                },
                {
                    'name': 'Greenpeace International',
                    'url': 'https://www.greenpeace.org/international/',
                    'type': 'greenpeace_intl'
                }
            ],
            'ja': [
                {
                    'name': '環境省',
                    'url': 'https://www.env.go.jp/',
                    'type': 'env_jp'
                }
            ],
            'ko': [
                {
                    'name': '환경부',
                    'url': 'https://www.me.go.kr/',
                    'type': 'env_kr'
                }
            ]
        }
    
    def get_latest_news(self, language: str = 'zh-TW', limit: int = 5) -> Optional[Dict]:
        """取得最新環保新聞"""
        try:
            news_items = []
            
            # 從不同來源爬取新聞
            for source in self.news_sources.get(language, self.news_sources['zh-TW']):
                try:
                    source_news = self._scrape_source(source, language)
                    if source_news:
                        news_items.extend(source_news)
                except Exception as e:
                    logger.warning(f"Error scraping {source['name']}: {str(e)}")
                    continue
            
            # 按時間排序並取最新的
            news_items.sort(key=lambda x: x.get('published_at', ''), reverse=True)
            latest_news = news_items[:limit]
            
            if latest_news:
                # 返回第一則新聞
                return latest_news[0]
            else:
                # 如果沒有爬取到新聞，返回預設內容
                return self._get_default_news(language)
                
        except Exception as e:
            logger.error(f"Error getting latest news: {str(e)}")
            return self._get_default_news(language)
    
    def _scrape_source(self, source: Dict, language: str) -> List[Dict]:
        """爬取特定來源的新聞"""
        news_items = []
        
        try:
            response = self.session.get(source['url'], timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if source['type'] == 'epa':
                news_items = self._scrape_epa_news(soup)
            elif source['type'] == 'einfo':
                news_items = self._scrape_einfo_news(soup)
            elif source['type'] == 'greenpeace':
                news_items = self._scrape_greenpeace_news(soup)
            elif source['type'] == 'enn':
                news_items = self._scrape_enn_news(soup)
            elif source['type'] == 'env_jp':
                news_items = self._scrape_env_jp_news(soup)
            elif source['type'] == 'env_kr':
                news_items = self._scrape_env_kr_news(soup)
            
            # 為每個新聞項目添加來源資訊
            for item in news_items:
                item['source'] = source['name']
                item['language'] = language
            
        except Exception as e:
            logger.error(f"Error scraping {source['name']}: {str(e)}")
        
        return news_items
    
    def _scrape_epa_news(self, soup: BeautifulSoup) -> List[Dict]:
        """爬取環保署新聞"""
        news_items = []
        
        try:
            # 尋找新聞項目（根據實際網站結構調整）
            news_elements = soup.find_all(['div', 'article'], class_=['news-item', 'article-item'])
            
            for element in news_elements[:5]:  # 限制數量
                title_elem = element.find(['h1', 'h2', 'h3', 'a'], class_=['title', 'news-title'])
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '') if title_elem.name == 'a' else ''
                
                # 尋找摘要
                summary_elem = element.find(['p', 'div'], class_=['summary', 'excerpt'])
                summary = summary_elem.get_text(strip=True) if summary_elem else title[:100] + '...'
                
                # 尋找日期
                date_elem = element.find(['span', 'time'], class_=['date', 'publish-date'])
                date_str = date_elem.get_text(strip=True) if date_elem else datetime.now().strftime('%Y-%m-%d')
                
                news_items.append({
                    'title': title,
                    'summary': summary,
                    'url': link if link.startswith('http') else f"https://www.epa.gov.tw{link}",
                    'published_at': date_str
                })
                
        except Exception as e:
            logger.error(f"Error scraping EPA news: {str(e)}")
        
        return news_items
    
    def _scrape_einfo_news(self, soup: BeautifulSoup) -> List[Dict]:
        """爬取環境資訊中心新聞"""
        news_items = []
        
        try:
            # 根據環境資訊中心的實際結構調整
            news_elements = soup.find_all(['article', 'div'], class_=['post', 'news-item'])
            
            for element in news_elements[:5]:
                title_elem = element.find(['h1', 'h2', 'h3', 'a'], class_=['entry-title', 'post-title'])
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '') if title_elem.name == 'a' else ''
                
                summary_elem = element.find(['div', 'p'], class_=['entry-summary', 'excerpt'])
                summary = summary_elem.get_text(strip=True) if summary_elem else title[:100] + '...'
                
                news_items.append({
                    'title': title,
                    'summary': summary,
                    'url': link if link.startswith('http') else f"https://e-info.org.tw{link}",
                    'published_at': datetime.now().strftime('%Y-%m-%d')
                })
                
        except Exception as e:
            logger.error(f"Error scraping E-Info news: {str(e)}")
        
        return news_items
    
    def _scrape_greenpeace_news(self, soup: BeautifulSoup) -> List[Dict]:
        """爬取綠色和平新聞"""
        news_items = []
        
        try:
            # 根據綠色和平網站的實際結構調整
            news_elements = soup.find_all(['article', 'div'], class_=['news-item', 'post'])
            
            for element in news_elements[:5]:
                title_elem = element.find(['h1', 'h2', 'h3', 'a'])
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '') if title_elem.name == 'a' else ''
                
                summary_elem = element.find(['p', 'div'], class_=['excerpt', 'summary'])
                summary = summary_elem.get_text(strip=True) if summary_elem else title[:100] + '...'
                
                news_items.append({
                    'title': title,
                    'summary': summary,
                    'url': link if link.startswith('http') else f"https://www.greenpeace.org{link}",
                    'published_at': datetime.now().strftime('%Y-%m-%d')
                })
                
        except Exception as e:
            logger.error(f"Error scraping Greenpeace news: {str(e)}")
        
        return news_items
    
    def _scrape_enn_news(self, soup: BeautifulSoup) -> List[Dict]:
        """爬取 Environmental News Network 新聞"""
        news_items = []
        
        try:
            news_elements = soup.find_all(['article', 'div'], class_=['news-item', 'post'])
            
            for element in news_elements[:5]:
                title_elem = element.find(['h1', 'h2', 'h3', 'a'])
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '') if title_elem.name == 'a' else ''
                
                summary_elem = element.find(['p', 'div'], class_=['excerpt', 'summary'])
                summary = summary_elem.get_text(strip=True) if summary_elem else title[:100] + '...'
                
                news_items.append({
                    'title': title,
                    'summary': summary,
                    'url': link if link.startswith('http') else f"https://www.enn.com{link}",
                    'published_at': datetime.now().strftime('%Y-%m-%d')
                })
                
        except Exception as e:
            logger.error(f"Error scraping ENN news: {str(e)}")
        
        return news_items
    
    def _scrape_env_jp_news(self, soup: BeautifulSoup) -> List[Dict]:
        """爬取日本環境省新聞"""
        news_items = []
        
        try:
            news_elements = soup.find_all(['article', 'div'], class_=['news-item', 'post'])
            
            for element in news_elements[:5]:
                title_elem = element.find(['h1', 'h2', 'h3', 'a'])
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '') if title_elem.name == 'a' else ''
                
                summary_elem = element.find(['p', 'div'], class_=['excerpt', 'summary'])
                summary = summary_elem.get_text(strip=True) if summary_elem else title[:100] + '...'
                
                news_items.append({
                    'title': title,
                    'summary': summary,
                    'url': link if link.startswith('http') else f"https://www.env.go.jp{link}",
                    'published_at': datetime.now().strftime('%Y-%m-%d')
                })
                
        except Exception as e:
            logger.error(f"Error scraping ENV JP news: {str(e)}")
        
        return news_items
    
    def _scrape_env_kr_news(self, soup: BeautifulSoup) -> List[Dict]:
        """爬取韓國環境部新聞"""
        news_items = []
        
        try:
            news_elements = soup.find_all(['article', 'div'], class_=['news-item', 'post'])
            
            for element in news_elements[:5]:
                title_elem = element.find(['h1', 'h2', 'h3', 'a'])
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '') if title_elem.name == 'a' else ''
                
                summary_elem = element.find(['p', 'div'], class_=['excerpt', 'summary'])
                summary = summary_elem.get_text(strip=True) if summary_elem else title[:100] + '...'
                
                news_items.append({
                    'title': title,
                    'summary': summary,
                    'url': link if link.startswith('http') else f"https://www.me.go.kr{link}",
                    'published_at': datetime.now().strftime('%Y-%m-%d')
                })
                
        except Exception as e:
            logger.error(f"Error scraping ENV KR news: {str(e)}")
        
        return news_items
    
    def _get_default_news(self, language: str) -> Dict:
        """返回預設環保新聞"""
        default_news = {
            'zh-TW': {
                'title': '🌱 環保小知識：正確的垃圾分類',
                'summary': '垃圾分類是保護環境的重要行動。塑膠瓶要清洗後壓扁回收，紙類要避免沾濕，廚餘要與其他垃圾分開處理。每個人的小行動都能為地球帶來大改變！',
                'url': 'https://www.epa.gov.tw/',
                'published_at': datetime.now().strftime('%Y-%m-%d')
            },
            'en': {
                'title': '🌱 Environmental Tip: Proper Waste Sorting',
                'summary': 'Waste sorting is an important action to protect the environment. Plastic bottles should be cleaned and flattened before recycling, paper should be kept dry, and organic waste should be separated from other trash. Every small action can make a big difference for our planet!',
                'url': 'https://www.epa.gov/',
                'published_at': datetime.now().strftime('%Y-%m-%d')
            },
            'ja': {
                'title': '🌱 環境のヒント：正しいゴミ分別',
                'summary': 'ゴミ分別は環境保護のための重要な行動です。プラスチックボトルは洗って潰してからリサイクルし、紙類は濡らさないようにし、生ゴミは他のゴミと分けて処理します。一人一人の小さな行動が地球に大きな変化をもたらします！',
                'url': 'https://www.env.go.jp/',
                'published_at': datetime.now().strftime('%Y-%m-%d')
            },
            'ko': {
                'title': '🌱 환경 팁: 올바른 쓰레기 분리수거',
                'summary': '쓰레기 분리수거는 환경 보호를 위한 중요한 행동입니다. 플라스틱 병은 세척 후 압축하여 재활용하고, 종이는 젖지 않게 하며, 음식물 쓰레기는 다른 쓰레기와 분리하여 처리합니다. 모든 사람의 작은 행동이 지구에 큰 변화를 가져올 수 있습니다!',
                'url': 'https://www.me.go.kr/',
                'published_at': datetime.now().strftime('%Y-%m-%d')
            }
        }
        
        return default_news.get(language, default_news['zh-TW'])
    
    def get_environmental_tips(self, language: str = 'zh-TW') -> List[str]:
        """取得環保小貼士"""
        tips = {
            'zh-TW': [
                '♻️ 塑膠瓶回收前記得清洗乾淨並壓扁',
                '📄 紙類回收要避免沾濕或弄髒',
                '🍎 廚餘要與其他垃圾分開處理',
                '🔋 電池不可投入一般垃圾，需特別回收',
                '💡 使用可重複使用的購物袋',
                '🚰 隨身攜帶環保杯，減少一次性用品',
                '🌱 選擇包裝較少的產品',
                '♻️ 舊衣物可以捐贈或回收再利用'
            ],
            'en': [
                '♻️ Clean and flatten plastic bottles before recycling',
                '📄 Keep paper dry and clean for recycling',
                '🍎 Separate organic waste from other trash',
                '🔋 Never throw batteries in regular trash - recycle them',
                '💡 Use reusable shopping bags',
                '🚰 Carry a reusable water bottle',
                '🌱 Choose products with less packaging',
                '♻️ Donate or recycle old clothes'
            ],
            'ja': [
                '♻️ プラスチックボトルは洗って潰してからリサイクル',
                '📄 紙類は濡らさずにリサイクル',
                '🍎 生ゴミは他のゴミと分けて処理',
                '🔋 電池は一般ゴミに捨てずに特別回収',
                '💡 再利用可能な買い物袋を使用',
                '🚰 マイボトルを持参して使い捨てを減らす',
                '🌱 包装の少ない商品を選ぶ',
                '♻️ 古い服は寄付やリサイクルに出す'
            ],
            'ko': [
                '♻️ 플라스틱 병은 세척 후 압축하여 재활용',
                '📄 종이는 젖지 않게 하여 재활용',
                '🍎 음식물 쓰레기는 다른 쓰레기와 분리',
                '🔋 배터리는 일반 쓰레기에 버리지 말고 특별 수거',
                '💡 재사용 가능한 쇼핑백 사용',
                '🚰 텀블러를 휴대하여 일회용품 줄이기',
                '🌱 포장이 적은 제품 선택',
                '♻️ 헌 옷은 기부하거나 재활용'
            ]
        }
        
        return tips.get(language, tips['zh-TW'])
    
    def get_recycling_guide(self, category: str, language: str = 'zh-TW') -> Dict:
        """取得特定類別的回收指南"""
        guides = {
            'zh-TW': {
                'plastic': {
                    'title': '塑膠類回收指南',
                    'steps': [
                        '1. 清洗乾淨，去除食物殘渣',
                        '2. 撕掉標籤和膠帶',
                        '3. 壓扁以節省空間',
                        '4. 投入塑膠類回收桶'
                    ],
                    'tips': '注意：保麗龍餐具不可回收，需當一般垃圾處理'
                },
                'paper': {
                    'title': '紙類回收指南',
                    'steps': [
                        '1. 保持乾燥，避免沾濕',
                        '2. 撕掉膠帶和訂書針',
                        '3. 整理平整',
                        '4. 投入紙類回收桶'
                    ],
                    'tips': '注意：衛生紙、面紙不可回收'
                }
            }
        }
        
        return guides.get(language, guides['zh-TW']).get(category, {})
