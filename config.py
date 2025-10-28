import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LINE Bot 設定
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
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
        'en': 'English'
    }
    
    # 垃圾分類類別
    WASTE_CATEGORIES = {
        'food': '廚餘',
        'paper': '紙類',
        'plastic': '塑膠類',
        'metal': '金屬類',
        'glass': '玻璃類',
        'textile': '紡織品',
        'ewaste': '電子廢棄物',
        'hazard': '有害垃圾',
        'bulky': '大型廢棄物',
        'animal': '動物屍體',
        'money': '金錢(貨幣)',
        'chat': '聊天訊息',
        'other': '其他/一般垃圾'
    }





