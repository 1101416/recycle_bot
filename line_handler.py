import os
import tempfile
import requests
from linebot.models import (
    TextMessage, TextSendMessage, ImageMessage, LocationMessage, PostbackEvent,
    TemplateSendMessage, CarouselTemplate, CarouselColumn,
    PostbackAction, MessageAction, URIAction, FlexSendMessage, BubbleContainer, BoxComponent, TextComponent,
    SeparatorComponent, IconComponent, ButtonComponent
)
import logging
from typing import List, Dict
from config import Config
from image_classifier import ImageClassifier
from recycle_db import RecycleDatabase
# 原本： from garbage_truck_api import GarbageTruckAPI
from garbage_truck_api import NewTaipeiTruckAPI

logger = logging.getLogger(__name__)

# --- 多語言文案庫 (已加入位置相關文案) ---
TEXTS = {
    'zh-TW': {
        'welcome_title': '🌱 AI 智能垃圾分類助手',
        'welcome_body': '歡迎使用！\n我可以幫您：\n• 📸 拍照識別垃圾類型\n• 📍 傳送位置查詢附近垃圾車\n\n請拍照上傳或傳送您的位置！',
        'help': '📖 使用說明\n\n🔸 拍照分類\n直接上傳垃圾照片，我會自動識別並提供回收方式。\n\n🔸 位置查詢\n傳送您的位置資訊，我會尋找附近的垃圾車。\n\n🔸 文字指令\n• /help - 查看幫助\n• /language - 語言設定\n• /news - 最新相關公告/新聞',
        'lang_selected': '🌎語言已設定為：繁體中文',
        'result_title': '🔍 垃圾分類結果',
        'result_item': '辨識物品',
        'result_category': '類別',
        'result_method': '處理方式',
        'result_tips': '小提醒',
        'error_unrecognized': '抱歉，無法識別這張圖片中的垃圾類型。\n請確保：\n• 圖片清晰\n• 垃圾在圖片中佔主要部分\n• 光線充足\n\n請重新拍照或嘗試其他圖片。',
        'default_reply': '請上傳垃圾照片進行分類，或輸入 /help 查看完整功能！',

        'location_title': '📍 附近垃圾車資訊 (新北市)',
        'location_searching': '正在查詢您附近 2 公里內的新北市垃圾車，請稍候...',
        'location_not_found': '抱歉，目前在您附近 2 公里內找不到即時垃圾車資訊。',
        'location_api_error': '抱歉，查詢垃圾車資訊時發生錯誤，請稍後再試。',
        'news_not_configured': '抱歉，系統尚未設定新聞來源（NEWS_API_URL）。請聯絡管理員。',
        'news_no_items': '抱歉，目前沒有可顯示的新聞。'
    },
    'en': {
        'welcome_title': '🌱 AI Smart Waste Classification Assistant',
        'welcome_body': 'Welcome!\nI can help you:\n• 📸 Identify waste types from photos\n• 📍 Send location to find nearby garbage trucks\n\nPlease upload a photo or send your location!',
        'help': '📖 User Guide\n\n🔸 Photo Classification\nUpload a photo of waste for automatic identification.\n\n🔸 Location Service\nSend your location to find nearby garbage trucks.\n\n🔸 Text Commands\n• /help - Help\n• /language - Language Settings\n• /news - Latest announcements/news',
        'lang_selected': '🌎Language has been set to: English',
        'result_title': '🔍 Classification Result',
        'result_item': 'Identified Item',
        'result_category': 'Category',
        'result_method': 'Disposal Method',
        'result_tips': 'Tips',
        'error_unrecognized': 'Sorry, I couldn\'t recognize the item in this image.\nPlease try another photo.',
        'default_reply': 'Please upload a photo for classification, or type /help to see all commands!',
        'location_title': '📍 Nearby Garbage Trucks (New Taipei City)',
        'location_searching': 'Searching for garbage trucks within 2 km of your location, please wait...',
        'location_not_found': 'Sorry, no real-time garbage truck information found within 2 km of your location.',
        'location_api_error': 'Sorry, an error occurred while fetching garbage truck information. Please try again later.',
        'news_not_configured': 'Sorry, news source (NEWS_API_URL) is not configured. Contact admin.',
        'news_no_items': 'Sorry, no news items available at the moment.'
    }
}

class LineMessageHandler:
    def __init__(self, line_bot_api):
        self.line_bot_api = line_bot_api
        self.image_classifier = ImageClassifier()
        self.recycle_db = RecycleDatabase()
        # 初始化新北市垃圾車 API
        try:
            self.garbage_truck_api = NewTaipeiTruckAPI()
        except Exception:
            logger.exception("Failed to initialize NewTaipeiTruckAPI")
            self.garbage_truck_api = None

        # News config
        self.news_api_url = os.getenv("NEWS_API_URL")  # 可設定為回傳 JSON 的 endpoint
        self.news_timeout = int(os.getenv("NEWS_TIMEOUT_SEC", "6"))

    def _get_texts(self, lang_code):
        return TEXTS.get(lang_code, TEXTS['en'])

    def handle_postback(self, event):
        user_id = event.source.user_id
        postback_data = event.postback.data
        if postback_data.startswith('lang_'):
            lang_code = postback_data.split('_')[1]
            if self.recycle_db.update_user_language(user_id, lang_code):
                texts = self._get_texts(lang_code)
                self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['lang_selected']))

    def handle_text_message(self, event):
        user_id = event.source.user_id
        text = event.message.text.strip().lower()
        self.recycle_db.get_or_create_user(user_id)
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        texts = self._get_texts(user_lang)

        # 新增 /news 指令
        if text in ['/news', 'news', '最新消息', '公告']:
            try:
                news_text = self._get_news_text(user_lang)
                self.line_bot_api.reply_message(event.reply_token, TextMessage(text=news_text))
            except Exception:
                logger.exception("Error fetching news")
                self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts.get('news_no_items')))
            return

        # /help 與 /language 保留
        if text in ['/help', '幫助', 'help']:
            self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['help']))
        elif text in ['/language', '語言', 'language']:
            self._send_language_menu(event.reply_token)
        else:
            # default
            self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['default_reply']))

    def _get_news_text(self, user_lang: str) -> str:
        """
        嘗試從 NEWS_API_URL 取得新聞 JSON（彈性處理），回傳可直接發送給使用者的文字。
        格式化：1) 會嘗試找 articles/list/rows；2) 如果是 plain text，回傳前 1000 字
        """
        texts = self._get_texts(user_lang)
        if not self.news_api_url:
            return texts.get('news_not_configured')

        try:
            r = requests.get(self.news_api_url, timeout=self.news_timeout)
            r.raise_for_status()
            # 優先嘗試 JSON
            try:
                data = r.json()
            except Exception:
                # 若不是 JSON，就把純文字當作一則新聞摘要
                txt = r.text.strip()
                return txt[:1500] if len(txt) > 1500 else txt

            # data 若為 dict 且包含常見欄位 articles/value/rows/data
            items = []
            if isinstance(data, dict):
                for key in ('articles','value','rows','data','items','results'):
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
                # 若 data 本身看起來就是 list-like under a hall field
                if not items:
                    # try common top-level list
                    for v in data.values():
                        if isinstance(v, list):
                            items = v
                            break
            elif isinstance(data, list):
                items = data

            # 解析 items，找 title/url/summary
            news_list = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                title = it.get('title') or it.get('標題') or it.get('titleText') or it.get('newsTitle') or None
                url = it.get('url') or it.get('link') or it.get('href') or it.get('newsUrl') or None
                summary = it.get('summary') or it.get('description') or it.get('摘要') or it.get('body') or ''
                if title:
                    news_list.append({'title': str(title).strip(), 'url': str(url).strip() if url else None, 'summary': str(summary).strip() if summary else ''})
                # stop early if many
                if len(news_list) >= 5:
                    break

            if not news_list:
                return texts.get('news_no_items')

            # format text: top 3
            lines = []
            for i, n in enumerate(news_list[:5], start=1):
                if n.get('url'):
                    lines.append(f"{i}. {n['title']}\n{n['url']}")
                else:
                    lines.append(f"{i}. {n['title']}\n{n.get('summary','')[:120]}")
            return "\n\n".join(lines)
        except Exception as e:
            logger.exception("Failed to fetch news from NEWS_API_URL")
            return texts.get('news_no_items')

    def handle_image_message(self, event):
        user_id = event.source.user_id
        self.recycle_db.get_or_create_user(user_id)
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        texts = self._get_texts(user_lang)
        try:
            message_content = self.line_bot_api.get_message_content(event.message.id)
            # line-bot-sdk 的 message_content.content 為 bytes (較常見)
            data_bytes = None
            try:
                data_bytes = getattr(message_content, "content", None)
            except Exception:
                data_bytes = None

            if not data_bytes:
                # try reading via iterator or .read()
                try:
                    # some SDK versions return an object with .content attribute that's bytes
                    # else try iter_content (requests-like) or read()
                    if hasattr(message_content, "iter_content"):
                        chunks = []
                        for ch in message_content.iter_content(1024):
                            chunks.append(ch)
                        data_bytes = b"".join(chunks)
                    elif hasattr(message_content, "read"):
                        data_bytes = message_content.read()
                except Exception:
                    data_bytes = None

            if not data_bytes:
                raise RuntimeError("Could not read image content from Line message")

            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(data_bytes)
                temp_file_path = temp_file.name

            try:
                classification_result = self.image_classifier.classify_image(temp_file_path)
                if classification_result:
                    # 儲存到 DB（仍記錄 confidence，但不顯示給使用者）
                    item_name_for_db = classification_result['item_name_zh'] if user_lang == 'zh-TW' else classification_result['item_name_en']
                    # classification_result['confidence'] 仍可寫入 DB
                    try:
                        self.recycle_db.record_classification(user_id, classification_result.get('category'), classification_result.get('confidence'))
                    except Exception:
                        logger.exception("Failed to record classification to DB")

                    waste_info = self.recycle_db.get_specific_waste_info(classification_result['category'], item_name_for_db, user_lang)
                    if waste_info:
                        # 回傳結果，但不包含信心度
                        self._send_classification_result(event.reply_token, classification_result, waste_info, texts, user_lang)
                    else:
                        self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))
                else:
                    self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))
            finally:
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
        except Exception as e:
            logger.exception(f"Error processing image: {e}")
            self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))

    def handle_location_message(self, event):
        user_id = event.source.user_id
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        texts = self._get_texts(user_lang)

        # 先回覆「正在查詢」
        try:
            self.line_bot_api.reply_message(event.reply_token, TextSendMessage(text=texts['location_searching']))
        except Exception:
            logger.exception("Failed to send searching reply")

        try:
            user_lat = getattr(event.message, "latitude", None)
            user_lng = getattr(event.message, "longitude", None)
            address = getattr(event.message, "address", "")

            nearby = []
            # 優先使用經緯度查詢（若有）
            if user_lat is not None and user_lng is not None and self.garbage_truck_api:
                try:
                    nearby = self.garbage_truck_api.get_schedules_by_location(user_lat, user_lng, radius_m=2000)
                except Exception:
                    logger.exception("Error calling get_schedules_by_location")

            # 若經緯度查詢沒結果，再 fallback 用 address
            if not nearby and address and self.garbage_truck_api:
                try:
                    nearby = self.garbage_truck_api.get_schedules_by_address(address, radius_m=2000)
                except Exception:
                    logger.exception("Error calling get_schedules_by_address")

            if nearby:
                try:
                    flex_message = self._create_trucks_flex_message(nearby, texts)
                    # 先前已 reply searching，所以用 push
                    self.line_bot_api.push_message(user_id, flex_message)
                except Exception:
                    logger.exception("Failed to send flex message; fallback to text")
                    brief = []
                    for s in nearby[:5]:
                        dist = f" ({s.get('_distance_m')}m)" if s.get('_distance_m') else ""
                        src_note = ""
                        if s.get('_synthetic'):
                            src_note = "（參考資料）"
                        elif s.get('_from_cache'):
                            src_note = "（快取）"
                        brief.append(f"{s.get('location')}{dist}\n{ s.get('time','') } {src_note}\n車號：{s.get('car')}")
                    self.line_bot_api.push_message(user_id, TextSendMessage(text="找到以下垃圾車資訊：\n\n" + "\n\n".join(brief)))
            else:
                self.line_bot_api.push_message(user_id, TextSendMessage(text=texts.get('location_not_found', '抱歉，找不到附近垃圾車資訊。')))
        except Exception:
            logger.exception("Error handling location message")
            self.line_bot_api.push_message(user_id, TextSendMessage(text=texts.get('location_api_error', '抱歉，查詢垃圾車資訊時發生錯誤，請稍後再試。')))

    def _send_language_menu(self, reply_token):
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(thumbnail_image_url='https://i.imgur.com/CoN90hA.png', title='繁體中文', text='選擇繁體中文介面', actions=[PostbackAction(label='選擇', data='lang_zh-TW')]),
            CarouselColumn(thumbnail_image_url='https://i.imgur.com/4l6A0p5.png', title='English', text='Select English interface', actions=[PostbackAction(label='Select', data='lang_en')])
        ])
        template_message = TemplateSendMessage(alt_text='語言選擇 / Language Selection', template=carousel_template)
        self.line_bot_api.reply_message(reply_token, template_message)

    def _send_user_stats(self, reply_token, user_id, user_lang):
        """
        保留舊函式，但不再由 /stats 觸發（你說不需要 /stats）。
        """
        try:
            stats = self.recycle_db.get_user_stats(user_id)
            texts = self._get_texts(user_lang)
            stats_text = f"{texts['stats_title']}\n\n"
            stats_text += f"🔸 {texts['stats_total']}：{stats['total_classifications']}\n"
            stats_text += f"🔸 {texts['stats_accuracy']}：{stats['accuracy_rate']:.1f}%\n"
            stats_text += f"🔸 {texts['stats_common']}：{stats['most_common_category']}\n"
            stats_text += f"🔸 {texts['stats_points']}：{stats['eco_points']}\n\n"
            stats_text += texts['stats_encourage']
            self.line_bot_api.reply_message(reply_token, TextMessage(text=stats_text))
        except Exception:
            logger.exception("Error sending user stats")

    def _create_trucks_flex_message(self, schedules: List[Dict], texts: Dict) -> FlexSendMessage:
        """建立「清運時間表」的 Flex Message 輪播卡片"""
        bubbles = []
        for schedule in schedules[:10]: # 最多顯示 10 筆結果
            # 顯示 time 並加上來源註記（如果有）
            time_text = schedule.get('time', '')
            if schedule.get('_synthetic'):
                time_text = f"{time_text}\n（系統提示：此資料為快取/參考，非即時）"
            elif schedule.get('_from_cache'):
                time_text = f"{time_text}\n（系統提示：使用本地快取資料）"

            bubble = BubbleContainer(
                direction='ltr',
                body=BoxComponent(
                    layout='vertical',
                    spacing='md',
                    contents=[
                        TextComponent(text=f"📍 {schedule['location']}", weight='bold', size='md', color='#1DB446', wrap=True),
                        TextComponent(text=f"🚛 {schedule.get('city','')} - {schedule.get('car','')}", size='xs', color='#AAAAAA', margin='md'),
                        SeparatorComponent(margin='lg'),
                        BoxComponent(
                            layout='vertical',
                            margin='lg',
                            spacing='sm',
                            contents=[
                                BoxComponent(
                                    layout='baseline', spacing='sm',
                                    contents=[
                                        TextComponent(text='預計時間', color='#aaaaaa', size='sm', flex=3),
                                        TextComponent(text=time_text, wrap=True, color='#666666', size='sm', flex=5, weight='bold')
                                    ]
                                )
                            ]
                        )
                    ]
                )
            )
            bubbles.append(bubble)

        carousel_contents = {"type": "carousel", "contents": [bubble.as_json_dict() for bubble in bubbles]}
        
        # 以 texts 裡的 location_title 為 alt_text；若沒有，使用預設
        alt_text = texts.get('location_title', '垃圾車清運時間表')

        return FlexSendMessage(
            alt_text=alt_text,
            contents=carousel_contents
        )

    # line_handler.py

    # ... (其他函式不變) ...

    def _create_result_flex_message(self, classification_result, waste_info, texts, user_lang):
        """
        建立分類結果的 Flex Message — (修正 2.0 版本)
        - 中文模式顯示 "紙類"
        - 英文模式顯示 "Paper (紙類)"
        """
        item_display_name = classification_result['item_name_en'] if user_lang == 'en' else classification_result['item_name_zh']
        
        # --- ### 修正 2.0 ### ---
        
        # 從 waste_info 獲取主分類的英文鍵名和中文名稱
        main_category_key = waste_info['category'] # 例如 'paper'
        main_category_zh = waste_info['category_name_zh'] # 例如 '紙類'

        category_display_text = ""
        if user_lang == 'en':
            # 英文模式：組合英文首字母大寫和中文
            english_name = main_category_key.capitalize()
            category_display_text = f"{english_name} ({main_category_zh})"
        else:
            # 中文模式：僅顯示中文主分類
            category_display_text = main_category_zh
            
        # --- ### 修正結束 ### ---

        bubble = BubbleContainer(
            direction='ltr',
            header=BoxComponent(layout='vertical', contents=[TextComponent(text=texts['result_title'], weight='bold', size='xl', color='#1DB446')]),
            body=BoxComponent(layout='vertical', spacing='lg', contents=[
                BoxComponent(layout='horizontal', contents=[
                    TextComponent(text=f"{texts['result_item']}:", size='sm', color='#555555', flex=4),
                    TextComponent(text=item_display_name, size='sm', color='#111111', align='end', flex=6, weight='bold')
                ]),
                BoxComponent(layout='horizontal', contents=[
                    TextComponent(text=f"📂 {texts['result_category']}:", size='sm', color='#555555', flex=4),
                    # 這裡使用我們修正後的 category_display_text
                    TextComponent(text=category_display_text, size='sm', color='#111111', align='end', flex=6)
                ]),
                SeparatorComponent(margin='md'),
                BoxComponent(layout='vertical', margin='lg', contents=[
                    TextComponent(text=f"♻️ {texts['result_method']}", weight='bold', size='md', margin='sm'),
                    TextComponent(text=waste_info['disposal_method'], wrap=True, size='sm', margin='md', color='#333333')
                ]),
                BoxComponent(layout='vertical', margin='lg', contents=[
                    TextComponent(text=f"💡 {texts['result_tips']}", weight='bold', size='md', margin='sm'),
                    TextComponent(text=waste_info.get('tips', '-'), wrap=True, size='sm', margin='md', color='#333333')
                ])
            ])
        )
        return FlexSendMessage(alt_text=texts['result_title'], contents=bubble)

    def _send_classification_result(self, reply_token, classification_result, waste_info, texts, user_lang):
        # 不顯示 confidence 給使用者
        flex_message = self._create_result_flex_message(classification_result, waste_info, texts, user_lang)
        self.line_bot_api.reply_message(reply_token, flex_message)

}

