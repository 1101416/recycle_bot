# 檔案: main.py
# (此版本已重新啟用排程器)

from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage, LocationMessage, PostbackEvent, FollowEvent
import os
import logging
from config import Config
from line_handler import LineMessageHandler
# --- vvv 修改處：重新啟用排程器 vvv ---
from scheduler import SchedulerManager
# --- ^^^ 修改處 ^^^ ---

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

if not getattr(Config, "LINE_CHANNEL_ACCESS_TOKEN", None) or not getattr(Config, "LINE_CHANNEL_SECRET", None):
    logger.warning("LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET not set in Config. Make sure these are configured for production.")

try:
    line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
except Exception:
    logger.exception("Failed to initialize LineBotApi/WebhookHandler. Check Config values.")
    line_bot_api = None
    handler = None

try:
    message_handler = LineMessageHandler(line_bot_api)
except Exception:
    logger.exception("Failed to initialize LineMessageHandler")
    message_handler = None

# --- vvv 修改處：重新啟用排程器 vvv ---
try:
    scheduler = SchedulerManager()
    scheduler.start()
    logger.info("Scheduler started successfully.")
except Exception:
    logger.exception("Failed to initialize or start SchedulerManager")
    scheduler = None
# --- ^^^ 修改處 ^^^ ---


@app.route("/", methods=["GET"])
def home():
    """首頁 - 健康檢查"""
    return "AI 智能垃圾分類 LINE Bot 運行中！"

@app.route("/webhook", methods=['POST'])
def webhook():
    """LINE Bot Webhook 端點"""
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        logger.warning("No X-Line-Signature found in request headers")
        abort(400)

    body = request.get_data(as_text=True)
    # logger.info(f"Request body: {body}") # (註解掉，避免 Log 太吵)

    if handler is None:
        logger.error("Webhook received but WebhookHandler is not initialized.")
        abort(500)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    except Exception as e:
        logger.exception(f"Error handling webhook: {e}")
        return 'OK', 200

    return 'OK', 200

@handler.add(FollowEvent)
def handle_follow(event):
    """處理加好友/解除封鎖事件"""
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process follow event.")
            return
        message_handler.handle_follow_event(event)
    except Exception as e:
        logger.exception(f"Error handling follow event: {e}")

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """處理文字訊息"""
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process text message.")
            return
        message_handler.handle_text_message(event)
    except Exception as e:
        logger.exception(f"Error handling text message: {e}")
        try:
            if line_bot_api:
                line_bot_api.reply_message(event.reply_token, TextMessage(text="抱歉，處理您的訊息時發生錯誤，請稍後再試。"))
        except Exception:
            logger.exception("Failed to send error reply for text message")

@handler.add(PostbackEvent)
def handle_postback(event):
    """處理 Postback 事件 (例如語言選擇)"""
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process postback.")
            return
        message_handler.handle_postback(event)
    except Exception as e:
        logger.exception(f"Error handling postback event: {e}")

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """處理圖片訊息"""
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process image message.")
            return
        message_handler.handle_image_message(event)
    except Exception as e:
        logger.exception(f"Error handling image message: {e}")
        try:
            if line_bot_api:
                line_bot_api.reply_message(event.reply_token, TextMessage(text="抱歉，處理您的圖片時發生錯誤，請稍後再試。"))
        except Exception:
            logger.exception("Failed to send error reply for image message")

@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    """處理位置訊息"""
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process location message.")
            return
        if not hasattr(message_handler, "handle_location_message"):
            logger.error("message_handler has no attribute 'handle_location_message'")
            if line_bot_api:
                try:
                    line_bot_api.reply_message(event.reply_token, TextMessage(text="抱歉，伺服器尚未啟用位置查詢功能，請稍後再試。"))
                except Exception:
                    logger.exception("Failed to reply about missing location handler")
            return
        message_handler.handle_location_message(event)
    except Exception as e:
        logger.exception(f"Error handling location message: {e}")
        try:
            if line_bot_api:
                line_bot_api.reply_message(event.reply_token, TextMessage(text="抱歉，處理您的位置資訊時發生錯誤，請稍後再試。"))
        except Exception:
            logger.exception("Failed to send error reply for location message")

@app.route("/test", methods=["GET"])
def test():
    """測試端點"""
    return jsonify({"status": "success", "message": "AI 智能垃圾分類 LINE Bot 測試成功！", "version": "1.0.0"}), 200

@app.route("/health", methods=["GET"])
def health_check():
    """健康檢查端點"""
    db_status = "unknown"
    try:
        # 簡易檢查：嘗試建立連線 (不依賴 recycle_db.py)
        with sqlite3.connect(Config.DATABASE_URL.replace("sqlite:///", "")) as conn:
             db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return jsonify({
        "status": "healthy",
        "services": {
            "line_bot": "running" if line_bot_api else "not_initialized",
            "database": db_status,
            "scheduler": "running" if (scheduler and scheduler.is_running()) else "disabled_or_failed"
        }
    }), 200

# 確保必要的目錄存在
os.makedirs('models', exist_ok=True)
os.makedirs('temp', exist_ok=True)
# os.makedirs('data', exist_ok=True) # (Render Disk 會自動處理 /data)

# 初始化資料庫
try:
    from database import init_database
    init_database()
    logger.info("Database initialized.")
except Exception:
    logger.exception("Failed to initialize database (init_database). Continuing but DB may be unavailable.")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
