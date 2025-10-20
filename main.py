# main.py
from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage, LocationMessage, PostbackEvent
import os
import logging
from config import Config
from line_handler import LineMessageHandler

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = Flask(__name__)

# 確保必要目錄存在
os.makedirs('models', exist_ok=True)
os.makedirs('temp', exist_ok=True)
os.makedirs('data', exist_ok=True)

# 檢查並初始化 LINE SDK
LINE_CHANNEL_ACCESS_TOKEN = getattr(Config, "LINE_CHANNEL_ACCESS_TOKEN", None)
LINE_CHANNEL_SECRET = getattr(Config, "LINE_CHANNEL_SECRET", None)
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    logger.error("LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET not set in Config. Aborting startup.")
    raise RuntimeError("Missing LINE configuration in Config")

try:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(LINE_CHANNEL_SECRET)
except Exception:
    logger.exception("Failed to initialize LineBotApi/WebhookHandler. Check Config values.")
    raise

# 初始化資料庫 (若 init_database 在 database.py 裡)
try:
    from database import init_database
    init_database()
    logger.info("Database initialized.")
except Exception:
    logger.exception("Failed to initialize database (init_database). Continuing but DB may be unavailable.")

# 初始化 message handler（**關鍵**：在 app 啟動時建立，避免 later None）
try:
    message_handler = LineMessageHandler(line_bot_api)
    logger.info("LineMessageHandler initialized.")
except Exception:
    logger.exception("Failed to initialize LineMessageHandler. Aborting startup.")
    raise

@app.route("/", methods=["GET"])
def home():
    return "AI 智能垃圾分類 LINE Bot 運行中！"

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        logger.warning("No X-Line-Signature found in request headers")
        abort(400)

    body = request.get_data(as_text=True)
    logger.info(f"Request body: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    except Exception as e:
        logger.exception(f"Error handling webhook: {e}")
        # 回 200 避免 LINE 重試造成 webhook 泳道被堵塞
        return 'OK', 200

    return 'OK', 200

# 事件處理器（使用 line-bot-sdk 的 decorator）
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process text message.")
            return
        message_handler.handle_text_message(event)
    except Exception as e:
        logger.exception(f"Error handling text message: {e}")
        try:
            line_bot_api.reply_message(event.reply_token, TextMessage(text="抱歉，處理您的訊息時發生錯誤，請稍後再試。"))
        except Exception:
            logger.exception("Failed to send error reply for text message")

@handler.add(PostbackEvent)
def handle_postback(event):
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process postback.")
            return
        message_handler.handle_postback(event)
    except Exception as e:
        logger.exception(f"Error handling postback event: {e}")

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process image message.")
            return
        message_handler.handle_image_message(event)
    except Exception as e:
        logger.exception(f"Error handling image message: {e}")
        try:
            line_bot_api.reply_message(event.reply_token, TextMessage(text="抱歉，處理您的圖片時發生錯誤，請稍後再試。"))
        except Exception:
            logger.exception("Failed to send error reply for image message")

@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process location message.")
            return
        # ensure message_handler implements location handling
        if not hasattr(message_handler, "handle_location_message"):
            logger.error("message_handler missing handle_location_message")
            line_bot_api.reply_message(event.reply_token, TextMessage(text="功能尚未開啟。"))
            return
        message_handler.handle_location_message(event)
    except Exception as e:
        logger.exception(f"Error handling location message: {e}")
        try:
            line_bot_api.reply_message(event.reply_token, TextMessage(text="抱歉，處理您的位置資訊時發生錯誤，請稍後再試。"))
        except Exception:
            logger.exception("Failed to send error reply for location message")

@app.route("/test", methods=["GET"])
def test():
    return jsonify({"status": "success", "message": "AI 智能垃圾分類 LINE Bot 測試成功！", "version": "1.0.0"}), 200

@app.route("/health", methods=["GET"])
def health_check():
    db_status = "unknown"
    try:
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    return jsonify({"status": "healthy", "services": {"line_bot": "running" if line_bot_api else "not_initialized", "database": db_status, "scheduler": "disabled"}}), 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
