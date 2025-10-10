import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LINE Bot 設定
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
    
    # 資料庫設定
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    
    # API 設定
    EPA_API_KEY = os.getenv('EPA_API_KEY')
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    
    # 推播設定
    PUSH_MESSAGE_ENABLED = os.getenv('PUSH_MESSAGE_ENABLED', 'true').lower() == 'true'
    
    # 模型設定
    MODEL_PATH = 'models/waste_classifier.h5'
    IMAGE_SIZE = (224, 224)
    
    # 簡化模式設定
    SIMPLE_MODE = True
    
    # 支援的語言
    SUPPORTED_LANGUAGES = {
        'zh-TW': '繁體中文',
        'en': 'English',
        'ja': '日本語',
        'ko': '한국어'
    }
    
    # 垃圾分類類別
    WASTE_CATEGORIES = {
        'plastic': '塑膠類',
        'paper': '紙類',
        'metal': '金屬類',
        'glass': '玻璃類',
        'organic': '廚餘',
        'battery': '電池',
        'electronics': '電子產品',
        'other': '其他'
    }
