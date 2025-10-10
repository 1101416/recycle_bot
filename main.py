from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, LocationMessage
import os
import logging
from config import Config
from line_handler import LineMessageHandler
from scheduler import SchedulerManager

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 初始化 LINE Bot API
line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)

# 初始化訊息處理器
message_handler = LineMessageHandler(line_bot_api)

# 初始化排程器
scheduler = SchedulerManager()
scheduler.start()

@app.route("/")
def home():
    """首頁 - 健康檢查"""
    return "AI 智能垃圾分類 LINE Bot 運行中！"

@app.route("/webhook", methods=['POST'])
def webhook():
    """LINE Bot Webhook 端點"""
    # 取得 X-Line-Signature header
    signature = request.headers.get('X-Line-Signature')
    
    if not signature:
        logger.warning("No signature found in request headers")
        abort(400)
    
    # 取得 request body
    body = request.get_data(as_text=True)
    logger.info(f"Request body: {body}")
    
    try:
        # 驗證簽名並處理事件
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        abort(500)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """處理文字訊息"""
    try:
        message_handler.handle_text_message(event)
    except Exception as e:
        logger.error(f"Error handling text message: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextMessage(text="抱歉，處理您的訊息時發生錯誤，請稍後再試。")
        )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """處理圖片訊息"""
    try:
        message_handler.handle_image_message(event)
    except Exception as e:
        logger.error(f"Error handling image message: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextMessage(text="抱歉，處理您的圖片時發生錯誤，請稍後再試。")
        )

@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    """處理位置訊息"""
    try:
        message_handler.handle_location_message(event)
    except Exception as e:
        logger.error(f"Error handling location message: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextMessage(text="抱歉，處理您的位置資訊時發生錯誤，請稍後再試。")
        )

@app.route("/test")
def test():
    """測試端點"""
    return {
        "status": "success",
        "message": "AI 智能垃圾分類 LINE Bot 測試成功！",
        "version": "1.0.0"
    }

@app.route("/health")
def health_check():
    """健康檢查端點"""
    return {
        "status": "healthy",
        "services": {
            "line_bot": "running",
            "database": "connected",
            "scheduler": "running" if scheduler.is_running() else "stopped"
        }
    }

# 確保必要的目錄存在
os.makedirs('models', exist_ok=True)
os.makedirs('temp', exist_ok=True)
os.makedirs('data', exist_ok=True)

# 初始化資料庫
from database import init_database
init_database()

if __name__ == "__main__":
    # 啟動應用程式
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
