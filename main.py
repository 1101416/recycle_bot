from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage, LocationMessage, PostbackEvent,FollowEvent
import os
import logging
from config import Config
from line_handler import LineMessageHandler
# from scheduler import SchedulerManager  # 暫時停用排程器

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 檢查必要 env（提醒但不強制中止）
if not getattr(Config, "LINE_CHANNEL_ACCESS_TOKEN", None) or not getattr(Config, "LINE_CHANNEL_SECRET", None):
    logger.warning("LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET not set in Config. Make sure these are configured for production.")

# 初始化 LINE Bot API
try:
    line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
except Exception:
    logger.exception("Failed to initialize LineBotApi/WebhookHandler. Check Config values.")
    # create placeholders to avoid crash (handlers should check message_handler existence)
    line_bot_api = None
    handler = None

# 初始化訊息處理器
try:
    message_handler = LineMessageHandler(line_bot_api)
except Exception:
    logger.exception("Failed to initialize LineMessageHandler")
    message_handler = None

# 初始化排程器（暫時停用）
# scheduler = SchedulerManager()
# scheduler.start()

@app.route("/", methods=["GET"])
def home():
    """首頁 - 健康檢查"""
    return "AI 智能垃圾分類 LINE Bot 運行中！"

@app.route("/webhook", methods=['POST'])
def webhook():
    """LINE Bot Webhook 端點"""
    # 取得 X-Line-Signature header
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        logger.warning("No X-Line-Signature found in request headers")
        abort(400)

    # 取得 request body
    body = request.get_data(as_text=True)
    logger.info(f"Request body: {body}")

    if handler is None:
        logger.error("Webhook received but WebhookHandler is not initialized.")
        abort(500)

    try:
        # 驗證簽名並處理事件（line-bot-sdk 會把事件分派給已註冊的 handler）
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    except Exception as e:
        # 記錄完整錯誤但回 200 給 LINE（可依需求改為 500）
        logger.exception(f"Error handling webhook: {e}")
        # 回 200 仍可避免 LINE 端大量重試導致 webhook 泳道塞車，
        # 但若你要讓 LINE 知道錯誤，改用 abort(500)
        return 'OK', 200

    return 'OK', 200

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
                line_bot_api.reply_message(
                    event.reply_token,
                    TextMessage(text="抱歉，處理您的訊息時發生錯誤，請稍後再試。")
                )
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
        # Postback 一般不需要回覆，但你可以選擇回覆或記錄

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
                line_bot_api.reply_message(
                    event.reply_token,
                    TextMessage(text="抱歉，處理您的圖片時發生錯誤，請稍後再試。")
                )
        except Exception:
            logger.exception("Failed to send error reply for image message")

@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    """處理位置訊息"""
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process location message.")
            return
        # 確保 handler 有 handle_location_message 方法
        if not hasattr(message_handler, "handle_location_message"):
            logger.error("message_handler has no attribute 'handle_location_message'")
            # 盡量回覆使用者
            if line_bot_api:
                try:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextMessage(text="抱歉，伺服器尚未啟用位置查詢功能，請稍後再試。")
                    )
                except Exception:
                    logger.exception("Failed to reply about missing location handler")
            return

        message_handler.handle_location_message(event)
    except Exception as e:
        logger.exception(f"Error handling location message: {e}")
        try:
            if line_bot_api:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextMessage(text="抱歉，處理您的位置資訊時發生錯誤，請稍後再試。")
                )
        except Exception:
            logger.exception("Failed to send error reply for location message")
            
@handler.add(FollowEvent)
def handle_follow(event):
    """處理加好友/解除封鎖事件"""
    try:
        if not message_handler:
            logger.error("message_handler not initialized; cannot process follow event.")
            return
        # 呼叫 line_handler.py 中的新方法
        message_handler.handle_follow_event(event)
    except Exception as e:
        logger.exception(f"Error handling follow event: {e}")

@app.route("/test", methods=["GET"])
def test():
    """測試端點"""
    return jsonify({
        "status": "success",
        "message": "AI 智能垃圾分類 LINE Bot 測試成功！",
        "version": "1.0.0"
    }), 200

@app.route("/health", methods=["GET"])
def health_check():
    """健康檢查端點"""
    # 嘗試檢查資料庫初始化結果（若 init_database 已在啟動時執行）
    db_status = "unknown"
    try:
        # 若你的 database 模組有檢查函式可呼叫，請改成真實檢查
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return jsonify({
        "status": "healthy",
        "services": {
            "line_bot": "running" if line_bot_api else "not_initialized",
            "database": db_status,
            "scheduler": "disabled"
        }
    }), 200

# 確保必要的目錄存在
os.makedirs('models', exist_ok=True)
os.makedirs('temp', exist_ok=True)
os.makedirs('data', exist_ok=True)

# 初始化資料庫
try:
    from database import init_database
    init_database()
    logger.info("Database initialized.")
except Exception:
    logger.exception("Failed to initialize database (init_database). Continuing but DB may be unavailable.")

if __name__ == "__main__":
    # 啟動應用程式
    port = int(os.environ.get('PORT', 5000))
    # 關閉 debug 模式以避免在 production 泄露細節
    app.run(host='0.0.0.0', port=port, debug=False)

