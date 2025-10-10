import os
import tempfile
import requests
from linebot.models import (
    TextMessage, ImageMessage, LocationMessage, 
    TemplateSendMessage, CarouselTemplate, CarouselColumn,
    PostbackAction, MessageAction, URIAction,
    QuickReply, QuickReplyButton, PostbackTemplateAction
)
from linebot.exceptions import LineBotApiError
import logging
from config import Config
from image_classifier import ImageClassifier
from recycle_db import RecycleDatabase
# from news_scraper import NewsScraper  # 暫時停用

logger = logging.getLogger(__name__)

class LineMessageHandler:
    def __init__(self, line_bot_api):
        self.line_bot_api = line_bot_api
        self.image_classifier = ImageClassifier()
        self.recycle_db = RecycleDatabase()
        # self.news_scraper = NewsScraper()  # 暫時停用
    
    def handle_text_message(self, event):
        """處理文字訊息"""
        user_id = event.source.user_id
        text = event.message.text.strip()
        
        # 取得使用者語言偏好
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        
        # 處理不同類型的文字指令
        if text in ['/start', '開始', 'start', '開始使用']:
            self._send_welcome_message(event.reply_token, user_lang)
        elif text in ['/help', '幫助', 'help', '使用說明']:
            self._send_help_message(event.reply_token, user_lang)
        elif text in ['/language', '語言', 'language', '語言設定']:
            self._send_language_menu(event.reply_token)
        elif text in ['/news', '新聞', 'news', '環保新聞']:
            self._send_news_message(event.reply_token, user_lang)
        elif text in ['/stats', '統計', 'stats', '我的統計']:
            self._send_user_stats(event.reply_token, user_id, user_lang)
        elif text.startswith('/search '):
            # 搜尋特定垃圾的處理方式
            search_term = text[8:].strip()
            self._search_waste_info(event.reply_token, search_term, user_lang)
        else:
            # 預設回覆
            self._send_default_reply(event.reply_token, user_lang)
    
    def handle_image_message(self, event):
        """處理圖片訊息"""
        user_id = event.source.user_id
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        
        try:
            # 下載圖片
            message_content = self.line_bot_api.get_message_content(event.message.id)
            image_data = b''
            for chunk in message_content.iter_content():
                image_data += chunk
            
            # 儲存臨時圖片
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(image_data)
                temp_file_path = temp_file.name
            
            try:
                # 進行垃圾分類
                classification_result = self.image_classifier.classify_image(temp_file_path)
                
                if classification_result:
                    # 取得詳細的回收資訊
                    waste_info = self.recycle_db.get_waste_info(
                        classification_result['category'], 
                        user_lang
                    )
                    
                    # 記錄使用者的分類行為
                    self.recycle_db.record_classification(
                        user_id, 
                        classification_result['category'],
                        classification_result['confidence']
                    )
                    
                    # 回覆分類結果
                    self._send_classification_result(
                        event.reply_token, 
                        classification_result, 
                        waste_info, 
                        user_lang
                    )
                else:
                    self._send_classification_error(event.reply_token, user_lang)
                    
            finally:
                # 清理臨時檔案
                os.unlink(temp_file_path)
                
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            self._send_classification_error(event.reply_token, user_lang)
    
    def handle_location_message(self, event):
        """處理位置訊息"""
        user_id = event.source.user_id
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        
        latitude = event.message.latitude
        longitude = event.message.longitude
        
        # 查詢附近的垃圾車時間或回收站
        self._send_location_info(event.reply_token, latitude, longitude, user_lang)
    
    def _send_welcome_message(self, reply_token, user_lang):
        """發送歡迎訊息"""
        messages = {
            'zh-TW': {
                'title': '🌱 AI 智能垃圾分類助手',
                'text': '歡迎使用 AI 智能垃圾分類 LINE Bot！\n\n我可以幫您：\n• 📸 拍照識別垃圾類型\n• ♻️ 提供回收處理方式\n• 📰 分享環保新聞\n• 🗺️ 查詢附近回收站\n\n請拍照上傳垃圾圖片，或輸入 /help 查看完整功能！'
            },
            'en': {
                'title': '🌱 AI Smart Waste Classification Assistant',
                'text': 'Welcome to AI Smart Waste Classification LINE Bot!\n\nI can help you:\n• 📸 Take photos to identify waste types\n• ♻️ Provide recycling methods\n• 📰 Share environmental news\n• 🗺️ Find nearby recycling stations\n\nPlease upload a photo of waste or type /help for full features!'
            },
            'ja': {
                'title': '🌱 AI スマートゴミ分別アシスタント',
                'text': 'AI スマートゴミ分別 LINE Bot へようこそ！\n\n私ができること：\n• 📸 写真を撮ってゴミの種類を識別\n• ♻️ リサイクル方法を提供\n• 📰 環境ニュースを共有\n• 🗺️ 近くのリサイクルステーションを検索\n\nゴミの写真をアップロードするか、/help と入力して全機能を確認してください！'
            },
            'ko': {
                'title': '🌱 AI 스마트 쓰레기 분류 어시스턴트',
                'text': 'AI 스마트 쓰레기 분류 LINE Bot에 오신 것을 환영합니다!\n\n제가 도와드릴 수 있는 것들:\n• 📸 사진을 찍어 쓰레기 종류 식별\n• ♻️ 재활용 방법 제공\n• 📰 환경 뉴스 공유\n• 🗺️ 근처 재활용소 검색\n\n쓰레기 사진을 업로드하거나 /help를 입력하여 전체 기능을 확인하세요!'
            }
        }
        
        message = messages.get(user_lang, messages['zh-TW'])
        
        self.line_bot_api.reply_message(
            reply_token,
            TextMessage(text=f"{message['title']}\n\n{message['text']}")
        )
    
    def _send_help_message(self, reply_token, user_lang):
        """發送幫助訊息"""
        help_texts = {
            'zh-TW': """📖 使用說明

🔸 拍照分類
直接上傳垃圾照片，我會自動識別並提供回收方式

🔸 文字指令
• /start - 開始使用
• /help - 查看幫助
• /language - 語言設定
• /news - 環保新聞
• /stats - 我的統計
• /search [垃圾名稱] - 搜尋特定垃圾

🔸 位置功能
傳送位置資訊可查詢附近回收站和垃圾車時間

🔸 多語言支援
支援繁體中文、英文、日文、韓文

有任何問題請隨時詢問！""",
            'en': """📖 User Guide

🔸 Photo Classification
Upload waste photos directly, I'll automatically identify and provide recycling methods

🔸 Text Commands
• /start - Start using
• /help - View help
• /language - Language settings
• /news - Environmental news
• /stats - My statistics
• /search [waste name] - Search specific waste

🔸 Location Feature
Send location info to find nearby recycling stations and garbage truck schedules

🔸 Multi-language Support
Supports Traditional Chinese, English, Japanese, Korean

Feel free to ask if you have any questions!""",
            'ja': """📖 使用説明

🔸 写真分類
ゴミの写真を直接アップロードすると、自動で識別してリサイクル方法を提供します

🔸 テキストコマンド
• /start - 使用開始
• /help - ヘルプ表示
• /language - 言語設定
• /news - 環境ニュース
• /stats - 私の統計
• /search [ゴミ名] - 特定のゴミを検索

🔸 位置機能
位置情報を送信すると、近くのリサイクルステーションやゴミ収集車の時間を検索できます

🔸 多言語サポート
繁体字中国語、英語、日本語、韓国語をサポート

ご質問がございましたらお気軽にお聞きください！""",
            'ko': """📖 사용 설명서

🔸 사진 분류
쓰레기 사진을 직접 업로드하면 자동으로 식별하여 재활용 방법을 제공합니다

🔸 텍스트 명령어
• /start - 사용 시작
• /help - 도움말 보기
• /language - 언어 설정
• /news - 환경 뉴스
• /stats - 내 통계
• /search [쓰레기 이름] - 특정 쓰레기 검색

🔸 위치 기능
위치 정보를 전송하면 근처 재활용소와 쓰레기 수거차 시간을 검색할 수 있습니다

🔸 다국어 지원
번체 중국어, 영어, 일본어, 한국어 지원

궁금한 점이 있으시면 언제든지 문의하세요!"""
        }
        
        text = help_texts.get(user_lang, help_texts['zh-TW'])
        self.line_bot_api.reply_message(reply_token, TextMessage(text=text))
    
    def _send_language_menu(self, reply_token):
        """發送語言選擇選單"""
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(
                thumbnail_image_url='https://via.placeholder.com/300x200/4CAF50/FFFFFF?text=繁體中文',
                title='繁體中文',
                text='選擇繁體中文介面',
                actions=[PostbackAction(label='選擇', data='lang_zh-TW')]
            ),
            CarouselColumn(
                thumbnail_image_url='https://via.placeholder.com/300x200/2196F3/FFFFFF?text=English',
                title='English',
                text='Select English interface',
                actions=[PostbackAction(label='Select', data='lang_en')]
            ),
            CarouselColumn(
                thumbnail_image_url='https://via.placeholder.com/300x200/FF9800/FFFFFF?text=日本語',
                title='日本語',
                text='日本語インターフェースを選択',
                actions=[PostbackAction(label='選択', data='lang_ja')]
            ),
            CarouselColumn(
                thumbnail_image_url='https://via.placeholder.com/300x200/9C27B0/FFFFFF?text=한국어',
                title='한국어',
                text='한국어 인터페이스 선택',
                actions=[PostbackAction(label='선택', data='lang_ko')]
            )
        ])
        
        template_message = TemplateSendMessage(
            alt_text='語言選擇 / Language Selection',
            template=carousel_template
        )
        
        self.line_bot_api.reply_message(reply_token, template_message)
    
    def _send_news_message(self, reply_token, user_lang):
        """發送環保新聞"""
        try:
            # 暫時使用預設新聞
            news_text = "📰 環保小知識\n\n♻️ 正確的垃圾分類是保護環境的重要行動！\n\n• 塑膠瓶要清洗後壓扁回收\n• 紙類要避免沾濕\n• 廚餘要與其他垃圾分開處理\n\n讓我們一起為地球盡一份心力！🌱"
            self.line_bot_api.reply_message(reply_token, TextMessage(text=news_text))
        except Exception as e:
            logger.error(f"Error sending news: {str(e)}")
            self.line_bot_api.reply_message(reply_token, TextMessage(text="獲取新聞時發生錯誤，請稍後再試。"))
    
    def _send_user_stats(self, reply_token, user_id, user_lang):
        """發送使用者統計資訊"""
        stats = self.recycle_db.get_user_stats(user_id)
        
        stats_text = f"📊 您的環保統計\n\n"
        stats_text += f"🔸 總分類次數：{stats['total_classifications']}\n"
        stats_text += f"🔸 正確分類率：{stats['accuracy_rate']:.1f}%\n"
        stats_text += f"🔸 最常分類：{stats['most_common_category']}\n"
        stats_text += f"🔸 環保積分：{stats['eco_points']}\n\n"
        stats_text += "繼續保持環保好習慣！🌱"
        
        self.line_bot_api.reply_message(reply_token, TextMessage(text=stats_text))
    
    def _search_waste_info(self, reply_token, search_term, user_lang):
        """搜尋特定垃圾資訊"""
        waste_info = self.recycle_db.search_waste_by_name(search_term, user_lang)
        
        if waste_info:
            info_text = f"🔍 搜尋結果：{search_term}\n\n"
            info_text += f"📂 分類：{waste_info['category']}\n"
            info_text += f"♻️ 處理方式：\n{waste_info['disposal_method']}\n"
            if waste_info['tips']:
                info_text += f"\n💡 小提醒：{waste_info['tips']}"
            
            self.line_bot_api.reply_message(reply_token, TextMessage(text=info_text))
        else:
            no_result_text = f"找不到「{search_term}」的相關資訊，請嘗試其他關鍵字或拍照上傳。"
            self.line_bot_api.reply_message(reply_token, TextMessage(text=no_result_text))
    
    def _send_classification_result(self, reply_token, classification_result, waste_info, user_lang):
        """發送分類結果"""
        confidence = classification_result['confidence']
        category = classification_result['category']
        
        result_text = f"🔍 垃圾分類結果\n\n"
        result_text += f"📂 類別：{waste_info['category_name']}\n"
        result_text += f"🎯 信心度：{confidence:.1f}%\n\n"
        result_text += f"♻️ 處理方式：\n{waste_info['disposal_method']}\n"
        
        if waste_info['tips']:
            result_text += f"\n💡 小提醒：{waste_info['tips']}"
        
        if confidence < 0.7:
            result_text += f"\n\n⚠️ 注意：信心度較低，建議您確認分類是否正確。"
        
        self.line_bot_api.reply_message(reply_token, TextMessage(text=result_text))
    
    def _send_classification_error(self, reply_token, user_lang):
        """發送分類錯誤訊息"""
        error_text = "抱歉，無法識別這張圖片中的垃圾類型。請確保：\n\n"
        error_text += "• 圖片清晰可見\n"
        error_text += "• 垃圾在圖片中佔主要部分\n"
        error_text += "• 光線充足\n\n"
        error_text += "請重新拍照或嘗試其他圖片。"
        
        self.line_bot_api.reply_message(reply_token, TextMessage(text=error_text))
    
    def _send_location_info(self, reply_token, latitude, longitude, user_lang):
        """發送位置相關資訊"""
        location_text = f"📍 位置資訊\n\n"
        location_text += f"緯度：{latitude}\n"
        location_text += f"經度：{longitude}\n\n"
        location_text += "正在查詢附近的回收站和垃圾車時間..."
        
        # 這裡可以整合政府開放資料 API
        # 暫時回覆基本訊息
        self.line_bot_api.reply_message(reply_token, TextMessage(text=location_text))
    
    def _send_default_reply(self, reply_token, user_lang):
        """發送預設回覆"""
        default_text = "請上傳垃圾照片進行分類，或輸入 /help 查看完整功能！"
        self.line_bot_api.reply_message(reply_token, TextMessage(text=default_text))

