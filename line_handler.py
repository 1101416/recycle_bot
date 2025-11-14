import os
import tempfile
import requests
from linebot.models import (
    TextMessage, TextSendMessage, ImageMessage, LocationMessage, PostbackEvent, FollowEvent,
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
        'maybe_chat_reply': """您說的是...？ 🤔
如果您想進行垃圾分類，請：
📸 直接傳送【照片】
✏️ 輸入【物品名稱】（例如：紙杯、電池）

或點選下方選單或輸入/help 查看更多功能喔！""",
        'not_garbage_reply': """🤔抱歉，這個好像不是實體的垃圾耶！
我主要擅長分類可以丟棄的實體物品。如果您傳送的是螢幕截圖、遊戲畫面或繪圖，我可能無法提供回收建議喔！""",
        'help': """📖 使用說明

📸 拍照分類
直接上傳垃圾照片，我會自動識別垃圾類別並提供回收方式

🔸 文字指令
• 輸入 /help - 查看幫助
• 輸入 /language - 顯示目前所支援的語言並提供選擇
• 輸入 /news - 環保新聞
• 輸入「欲做分類的垃圾名稱」 - 幫該垃圾做分類，如輸入：娃娃

📍 位置功能
• 傳送位置資訊可查詢附近垃圾車時間
• 輸入/clothes並傳送位置資訊可查詢附近舊衣回收箱

🌏 目前的語言支援
支援繁體中文、英文

或點選下方選單使用常用功能！""",
        
        'lang_selected': '🌎語言已設定為：繁體中文',
        'result_title': '🔍 垃圾分類結果',
        'result_item': '辨識物品',
        'result_category': '類別',
        'result_method': '處理方式',
        'result_tips': '小提醒',
        'error_unrecognized': '抱歉，無法識別這張圖片中的垃圾類型。\n請確保：\n• 圖片清晰\n• 垃圾在圖片中佔主要部分\n• 光線充足\n\n請嘗試拍攝垃圾上的產品名稱或文字輸入物品名稱。',
        'default_reply': '請上傳垃圾照片或輸入文字進行分類，或輸入 /help 查看完整功能！',
        'welcome_on_follow': """{nickname} 您好～👋
我是您的專屬環保小幫手 🤖 {account_name}！
以後，環保的大小事就交給我吧！💪

我可以幫您：
📸 拍照或打字，即時識別垃圾分類！
📍 傳送位置，查詢附近的垃圾車與回收點！
📰 推播最新的環保新聞與知識！

請直接拍照上傳，或傳送您的位置！
點選「功能說明」了解更多使用方式！
🌏 想用其他語言，請點「語言選擇」👇""",
        
        'location_title': '📍 附近垃圾車資訊 (新北市)',
        'location_searching': '正在查詢您附近 200 公尺內的新北市垃圾車，請稍候...',
        'location_not_found': '抱歉，目前在您附近 200 公尺內找不到即時垃圾車資訊。',
        'location_api_error': '抱歉，查詢垃圾車資訊時發生錯誤，請稍後再試。',
        'news_not_configured': '抱歉，系統尚未設定新聞來源（NEWS_API_URL）。請聯絡管理員。',
        'news_no_items': '抱歉，目前沒有可顯示的新聞。'
    },
    'en': {
        'welcome_on_follow': """Hi {nickname}! 👋
I'm {account_name}, your personal eco-assistant! 🤖
Leave the eco-tasks to me from now on! 💪

I can help you:
📸 Instantly identify waste by photo or text!
📍 Find nearby garbage trucks & recycling points with your location!
📰 Get the latest environmental news & tips!

Just send a photo or your location to start!
Click "Functions" to learn more about how to use me!
🌏 Want another language? Click "Language" below! 👇""",
        'welcome_title': '🌱 AI Smart Waste Classification Assistant',
        'welcome_body': 'Welcome!\nI can help you:\n• 📸 Identify waste types from photos\n• 📍 Send location to find nearby garbage trucks\n\nPlease upload a photo or send your location!',
        'lang_selected': '🌎Language has been set to: English',
        'help': """📖 User Guide

📸 Photo Classification
Upload a photo of waste, and I will automatically identify the category and provide recycling instructions.

🔸 Text Commands
• enter /help - Show this help message
• enter /language - Show supported languages and let you choose
• enter /news - Get environmental news
• Type the name of an item - I will classify it

📍 Location Features
• Send your location to find nearby garbage truck schedules
• enter /clothes and then send your location to find nearby clothing donation boxes

🌏 Supported Languages
Supports Traditional Chinese and English.

Or, use the rich menu below for common features!""",
        
        'result_title': '🔍 Classification Result',
        'not_garbage_reply': """🤔 Sorry, this doesn't seem to be physical waste!
I specialize in classifying physical items that you can dispose of. If you sent a screenshot, game screen, or drawing, I might not be able to provide recycling advice!""",
        'result_item': 'Identified Item',
        'result_category': 'Category',
        'result_method': 'Disposal Method',
        'result_tips': 'Tips',
        'maybe_chat_reply': """Hmm? What was that...? 🤔
If you want to classify waste, please:
📸 Send a [Photo] directly
✏️ Type the [Item Name] (e.g., paper cup, battery)

Or tap the menu below or type /help for more functions!""",
        'error_unrecognized': 'Sorry, I couldn’t recognize the type of waste in this image.\nPlease make sure :\n• The image is clear\n• The waste item is the main focus\n• The lighting is sufficient\n\nTry taking a photo that shows the product label or type name instead.',
        'default_reply': 'Please upload a photo or type text for classification, or type /help to see all commands!',
        'location_title': '📍 Nearby Garbage Trucks (New Taipei City)',
        'location_searching': 'Searching for garbage trucks within 200 m of your location, please wait...',
        'location_not_found': 'Sorry, no real-time garbage truck information found within 200 m of your location.',
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


    # 檔案: line_handler.py

    def handle_follow_event(self, event):
        """
        處理加好友事件 (新版邏輯):
        1. 偵測使用者 LINE 語言設定。
        2. 如果使用者是第一次加入，根據偵測到的語言設定預設值 (非中文則預設英文)。
        3. 如果使用者已存在 (例如解除封鎖後重新加入)，則使用資料庫中儲存的語言設定。
        4. 發送對應語言的歡迎訊息。
        """
        user_id = event.source.user_id
        detected_language = 'en' # 預設為英文

        # 1. 取得使用者 LINE Profile 並嘗試偵測語言
        try:
            profile = self.line_bot_api.get_profile(user_id)
            nickname = profile.display_name
            # 檢查 profile 物件是否有 language 屬性
            if hasattr(profile, 'language') and profile.language:
                user_line_lang = profile.language.lower()
                # 如果 LINE 語言設定是繁體中文或簡體中文，則預設為 zh-TW
                if user_line_lang.startswith('zh'):
                    detected_language = 'zh-TW'
                # (未來可加入 ja, ko 等判斷)
                # else: 預設就是 'en'
            logger.info(f"Detected LINE language for {user_id}: {profile.language}, setting initial lang to: {detected_language}")

        except Exception as e:
            logger.warning(f"Could not get profile or language for user {user_id}. Defaulting nickname and lang. Error: {e}")
            nickname = "朋友" # 預設暱稱
            # 語言維持預設 'en'

        # 2. 檢查使用者是否已存在於資料庫
        existing_user_lang = self.recycle_db.get_user_language(user_id)

        display_language = ''
        if existing_user_lang:
            # 3a. 使用者已存在 -> 使用資料庫中儲存的語言
            display_language = existing_user_lang
            # 更新最後活動時間
            self.recycle_db.update_user_language(user_id, existing_user_lang) # update_user_language 其實也會更新 last_active
            logger.info(f"Existing user {user_id} re-followed. Using saved language: {display_language}")
        else:
            # 3b. 使用者是新的 -> 使用偵測到的語言建立資料，並以此語言顯示歡迎訊息
            self.recycle_db.get_or_create_user(user_id, language=detected_language) # 這裡會創建使用者並設定語言
            display_language = detected_language
            logger.info(f"New user {user_id} followed. Setting language to detected: {display_language}")

        # 4. 根據最終決定的語言，取得文案並發送歡迎訊息
        texts = self._get_texts(display_language)

        try:
            bot_info = self.line_bot_api.get_bot_info()
            account_name = bot_info.display_name
        except Exception as e:
            logger.warning(f"Could not get bot info automatically: {e}. Using default name.")
            account_name = "GreenLine 智慧垃圾分類助理" # 您的備用名稱

        # 格式化歡迎訊息
        welcome_text = texts['welcome_on_follow'].format(
            nickname=nickname,
            account_name=account_name
        )

        # 回覆歡迎訊息
        try:
            self.line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=welcome_text)
            )
            logger.info(f"Sent welcome message to user {user_id} in {display_language}")
        except Exception as e:
            logger.exception(f"Failed to reply to follow event: {e}")

    def handle_postback(self, event):
        user_id = event.source.user_id
        postback_data = event.postback.data
        if postback_data.startswith('lang_'):
            lang_code = postback_data.split('_')[1]
            if self.recycle_db.update_user_language(user_id, lang_code):
                texts = self._get_texts(lang_code)
                self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['lang_selected']))

    def handle_text_message(self, event):
        """
        處理文字訊息 (v8 - 使用 AI 聊天判斷)：
        1. 檢查指令。
        2. 非指令 -> 送 AI 分類 (AI 會判斷是否為 chat)。
        3. 檢查 AI 結果是否為 'chat' -> 回覆提示。
        4. 檢查 AI 結果是否為非實體物品 -> 回覆提示。
        5. 正常顯示分類結果。
        """
        user_id = event.source.user_id
        raw_text = event.message.text.strip()
        command_text = raw_text.lower()

        self.recycle_db.get_or_create_user(user_id)
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        texts = self._get_texts(user_lang)

        try:
            # --- 1. 優先處理「指令」 ---
            if command_text in ['/help', '幫助', 'help']:
                self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['help']))
                return
            # ... (處理 /language, /news 的程式碼不變) ...
            if command_text in ['/language', '語言', 'language']:
                self._send_language_menu(event.reply_token)
                return
            if command_text in ['/news', 'news', '最新消息', '公告']:
                news_text = self._get_news_text(user_lang)
                self.line_bot_api.reply_message(event.reply_token, TextMessage(text=news_text))
                return

            # --- 2. 如果不是指令，則執行「AI 文字分類」 ---
            classification_result = self.image_classifier.classify_text(raw_text)

            if classification_result:
                category = classification_result.get('category')
                item_zh = classification_result.get('item_name_zh', '')
                item_en = classification_result.get('item_name_en', '').lower()

                # --- 3. **優先**檢查 AI 是否判定為聊天 ---
                if category == 'chat':
                    self.line_bot_api.reply_message(
                        event.reply_token,
                        TextMessage(text=texts['maybe_chat_reply']) # 使用相同的提示文案
                    )
                    logger.info(f"Input text '{raw_text}' was classified as 'chat' by AI. Sent maybe_chat_reply.")
                    # 不記錄這次 chat 分類到資料庫
                    return # 提早結束

                # --- 4. **然後才**檢查是否為非實體物品 ---
                # (這個檢查仍然需要，以防 AI 判斷截圖時出錯)
                if item_zh in ['螢幕截圖', '遊戲畫面', '繪圖'] or item_en in ['screenshot', 'game screen', 'drawing']:
                    self.line_bot_api.reply_message(
                        event.reply_token,
                        TextMessage(text=texts['not_garbage_reply'])
                    )
                    logger.info(f"Replied with not_garbage_reply for non-physical text input: {item_zh}/{item_en}")
                    return # 提早結束

                # --- 5. 執行正常的分類流程 ---
                item_name_for_db = item_zh if user_lang == 'zh-TW' else item_en
                try:
                    self.recycle_db.record_classification(user_id, category, classification_result.get('confidence'), image_path=None)
                except Exception:
                    logger.exception("Failed to record text classification to DB")

                waste_info = self.recycle_db.get_specific_waste_info(category, item_name_for_db, user_lang)

                if waste_info:
                    flex_message = self._create_result_flex_message(classification_result, waste_info, texts, user_lang)
                    self.line_bot_api.reply_message(event.reply_token, flex_message)
                else:
                    logger.error(f"AI returned category '{category}' but no matching rule found in DB for lang '{user_lang}'.")
                    self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))
            else:
                self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))

        except Exception as e:
            logger.exception(f"Error handling text message: {e}")
            try:
                self.line_bot_api.reply_message(
                    event.reply_token,
                    TextMessage(text=texts.get('error_unrecognized', 'Sorry, an error occurred.'))
                )
            except Exception:
                 logger.exception("Failed to send error reply for text message")

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
        """
        處理圖片訊息 (最終版邏輯)：
        1. 下載圖片。
        2. 將圖片傳送給 AI (Gemini) 進行分類。
        3. 檢查 AI 是否回傳非實體物品，若是則回覆提示。
        4. 使用 AI 回傳的 category，去資料庫搜尋詳細規則並回傳。
        """
        user_id = event.source.user_id
        self.recycle_db.get_or_create_user(user_id)
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        texts = self._get_texts(user_lang)
        temp_file_path = None # 初始化

        try:
            # --- 1. 下載圖片 ---
            message_content = self.line_bot_api.get_message_content(event.message.id)
            data_bytes = None
            try:
                # 標準 line-bot-sdk v1/v2
                data_bytes = message_content.content
            except AttributeError:
                 # 嘗試 line-bot-sdk v3 的讀取方式
                try:
                    if hasattr(message_content, "iter_content"):
                        chunks = [ch for ch in message_content.iter_content()]
                        data_bytes = b"".join(chunks)
                    elif hasattr(message_content, "read"):
                         data_bytes = message_content.read()
                except Exception as read_err:
                    logger.error(f"Failed to read image content using iter_content/read: {read_err}")
            except Exception as get_err:
                 logger.error(f"Failed to get image content attribute: {get_err}")


            if not data_bytes:
                raise RuntimeError("Could not read image content from Line message")

            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(data_bytes)
                temp_file_path = temp_file.name

            # --- 2. 將圖片傳送給 AI ---
            classification_result = self.image_classifier.classify_image(temp_file_path)

            if classification_result:
                # --- 3. 檢查是否為非實體物品 ---
                item_zh = classification_result.get('item_name_zh', '')
                item_en = classification_result.get('item_name_en', '').lower()
                if item_zh in ['螢幕截圖', '遊戲畫面', '繪圖'] or item_en in ['screenshot', 'game screen', 'drawing']:
                    self.line_bot_api.reply_message(
                        event.reply_token,
                        TextMessage(text=texts['not_garbage_reply'])
                    )
                    logger.info(f"Replied with not_garbage_reply for non-physical item: {item_zh}/{item_en}")
                    # 不需要 return，因為 finally 會處理檔案刪除
                else:
                    # --- 4. 執行正常的分類流程 ---
                    item_name_for_db = item_zh if user_lang == 'zh-TW' else item_en
                    try:
                        self.recycle_db.record_classification(
                            user_id,
                            classification_result.get('category'),
                            classification_result.get('confidence'),
                            image_path=None # 暫不儲存圖片路徑
                        )
                    except Exception:
                        logger.exception("Failed to record image classification to DB")

                    waste_info = self.recycle_db.get_specific_waste_info(
                        classification_result['category'],
                        item_name_for_db,
                        user_lang
                    )
                    if waste_info:
                        self._send_classification_result(event.reply_token, classification_result, waste_info, texts, user_lang)
                    else:
                        self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))
            else:
                 # AI 分類失敗
                self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))

        except Exception as e:
            logger.exception(f"Error processing image message: {e}")
            try:
                self.line_bot_api.reply_message(
                    event.reply_token,
                    TextMessage(text=texts.get('error_unrecognized', 'Sorry, an error occurred processing the image.'))
                )
            except Exception:
                 logger.exception("Failed to send error reply for image message")
        finally:
            # 確保暫存檔案被刪除
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    logger.info(f"Deleted temp image file: {temp_file_path}")
                except Exception as unlink_err:
                    logger.error(f"Error deleting temp image file {temp_file_path}: {unlink_err}")
    # --- ^^^ handle_image_message 結束 ^^^ ---
    
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
                    nearby = self.garbage_truck_api.get_schedules_by_location(user_lat, user_lng, radius_m=200)
                except Exception:
                    logger.exception("Error calling get_schedules_by_location")

            # 若經緯度查詢沒結果，再 fallback 用 address
            if not nearby and address and self.garbage_truck_api:
                try:
                    nearby = self.garbage_truck_api.get_schedules_by_address(address, radius_m=200)
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
            CarouselColumn(thumbnail_image_url='https://github.com/1101416/recycle_bot/blob/main/language.png?raw=true', title='繁體中文', text='選擇繁體中文介面', actions=[PostbackAction(label='選擇', data='lang_zh-TW')]),
            CarouselColumn(thumbnail_image_url='https://github.com/1101416/recycle_bot/blob/main/language.png?raw=true', title='English', text='Select English interface', actions=[PostbackAction(label='Select', data='lang_en')])
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























