import os
import tempfile
from linebot.models import (
    TextMessage, ImageMessage, LocationMessage, PostbackEvent,
    TemplateSendMessage, CarouselTemplate, CarouselColumn,
    PostbackAction, MessageAction, URIAction, FlexSendMessage, BubbleContainer, BoxComponent, TextComponent,
    SeparatorComponent, IconComponent, ButtonComponent
)
import logging
from config import Config
from image_classifier import ImageClassifier
from recycle_db import RecycleDatabase

logger = logging.getLogger(__name__)

# --- 多語言文案庫 ---
TEXTS = {
    'zh-TW': {
        'welcome_title': '🌱 AI 智能垃圾分類助手',
        'welcome_body': '歡迎使用！\n我可以幫您：\n• 📸 拍照識別垃圾類型\n• ♻️ 提供回收處理方式\n\n請拍照上傳垃圾圖片，或輸入 /help 查看完整功能！',
        'help': '📖 使用說明\n\n🔸 拍照分類\n直接上傳垃圾照片，我會自動識別並提供回收方式。\n\n🔸 文字指令\n• /start - 開始使用\n• /help - 查看幫助\n• /language - 語言設定\n• /stats - 我的統計',
        'lang_selected': '🌎語言已設定為：繁體中文',
        'stats_title': '📊 您的環保統計',
        'stats_total': '總分類次數',
        'stats_accuracy': '正確分類率',
        'stats_common': '最常分類',
        'stats_points': '環保積分',
        'stats_encourage': '繼續保持環保好習慣！🌱',
        'result_title': '🔍 垃圾分類結果',
        'result_item': '辨識物品',
        'result_category': '類別',
        'result_confidence': '信心度',
        'result_method': '處理方式',
        'result_tips': '小提醒',
        'error_unrecognized': '抱歉，無法識別這張圖片中的垃圾類型。\n請確保：\n• 圖片清晰\n• 垃圾在圖片中佔主要部分\n• 光線充足\n\n請重新拍照或嘗試其他圖片。',
        'default_reply': '請上傳垃圾照片進行分類，或輸入 /help 查看完整功能！'
    },
    'en': {
        'welcome_title': '🌱 AI Smart Waste Classification Assistant',
        'welcome_body': 'Welcome!\nI can help you:\n• 📸 Identify waste types from photos\n• ♻️ Provide recycling methods\n\nPlease upload a photo of waste or type /help for full features!',
        'help': '📖 User Guide\n\n🔸 Photo Classification\nUpload a photo of waste, and I will automatically identify it and provide recycling methods.\n\n🔸 Text Commands\n• /start - Start\n• /help - Help\n• /language - Language Settings\n• /stats - My Statistics',
        'lang_selected': '🌎Language has been set to: English',
        'stats_title': '📊 Your Eco Statistics',
        'stats_total': 'Total Classifications',
        'stats_accuracy': 'Accuracy Rate',
        'stats_common': 'Most Common Category',
        'stats_points': 'Eco Points',
        'stats_encourage': 'Keep up the great eco-friendly habits! 🌱',
        'result_title': '🔍 Classification Result',
        'result_item': 'Identified Item',
        'result_category': 'Category',
        'result_confidence': 'Confidence',
        'result_method': 'Disposal Method',
        'result_tips': 'Tips',
        'error_unrecognized': 'Sorry, I couldn\'t recognize the item in this image.\nPlease ensure:\n• The image is clear\n• The waste is the main subject\n• The lighting is good\n\nPlease try another photo.',
        'default_reply': 'Please upload a photo for classification, or type /help to see all commands!'
    }
    # 您可以繼續加入 'ja' 和 'ko' 的文案
}

class LineMessageHandler:
    def __init__(self, line_bot_api):
        self.line_bot_api = line_bot_api
        self.image_classifier = ImageClassifier()
        self.recycle_db = RecycleDatabase()

    def _get_texts(self, lang_code):
        """安全地取得文案，若無則回退到英文"""
        return TEXTS.get(lang_code, TEXTS['en'])

    def handle_postback(self, event):
        """處理 Postback 事件"""
        user_id = event.source.user_id
        postback_data = event.postback.data

        if postback_data.startswith('lang_'):
            lang_code = postback_data.split('_')[1]
            success = self.recycle_db.update_user_language(user_id, lang_code)
            
            if success:
                texts = self._get_texts(lang_code)
                reply_text = texts['lang_selected']
                self.line_bot_api.reply_message(event.reply_token, TextMessage(text=reply_text))

    def handle_text_message(self, event):
        """處理文字訊息"""
        user_id = event.source.user_id
        text = event.message.text.strip().lower()
        
        # 取得或創建使用者，並取得語言偏好
        self.recycle_db.get_or_create_user(user_id)
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        texts = self._get_texts(user_lang)
        
        if text in ['/start', '開始', 'start']:
            reply_text = f"{texts['welcome_title']}\n\n{texts['welcome_body']}"
            self.line_bot_api.reply_message(event.reply_token, TextMessage(text=reply_text))
        elif text in ['/help', '幫助', 'help']:
            self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['help']))
        elif text in ['/language', '語言', 'language']:
            self._send_language_menu(event.reply_token)
        elif text in ['/stats', '統計', 'stats']:
            self._send_user_stats(event.reply_token, user_id, user_lang)
        else:
            self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['default_reply']))

    def handle_image_message(self, event):
        """處理圖片訊息 (最終版)"""
        user_id = event.source.user_id
        self.recycle_db.get_or_create_user(user_id)
        user_lang = self.recycle_db.get_user_language(user_id) or 'zh-TW'
        texts = self._get_texts(user_lang)

        try:
            message_content = self.line_bot_api.get_message_content(event.message.id)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(message_content.content)
                temp_file_path = temp_file.name
            
            try:
                classification_result = self.image_classifier.classify_image(temp_file_path)
                
                if classification_result:
                    # 決定要用哪個語言的品項名稱去查詢資料庫
                    item_name_for_db = classification_result['item_name_zh'] if user_lang == 'zh-TW' else classification_result['item_name_en']
                    
                    waste_info = self.recycle_db.get_specific_waste_info(
                        classification_result['category'],
                        item_name_for_db,
                        user_lang
                    )
                    
                    if waste_info:
                        self.recycle_db.record_classification(
                            user_id, 
                            waste_info['category'],
                            classification_result['confidence']
                        )
                        self._send_classification_result(event.reply_token, classification_result, waste_info, texts, user_lang)
                    else:
                        self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))
                else:
                    self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))
            finally:
                os.unlink(temp_file_path)
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            self.line_bot_api.reply_message(event.reply_token, TextMessage(text=texts['error_unrecognized']))
            
    def _send_language_menu(self, reply_token):
        """發送美化後的語言選擇選單"""
        carousel_template = CarouselTemplate(columns=[
            CarouselColumn(
                # 使用台灣意象的圖片
                thumbnail_image_url='https://i.imgur.com/CoN90hA.png',
                title='繁體中文',
                text='選擇繁體中文介面',
                actions=[PostbackAction(label='選擇', data='lang_zh-TW')]
            ),
            CarouselColumn(
                # 使用英文意象的圖片
                thumbnail_image_url='https://i.imgur.com/4l6A0p5.png',
                title='English',
                text='Select English interface',
                actions=[PostbackAction(label='Select', data='lang_en')]
            )
        ])
        
        template_message = TemplateSendMessage(
            alt_text='語言選擇 / Language Selection',
            template=carousel_template
        )
        self.line_bot_api.reply_message(reply_token, template_message)


    
    def _send_user_stats(self, reply_token, user_id, user_lang):
        """發送使用者統計資訊"""
        stats = self.recycle_db.get_user_stats(user_id)
        texts = self._get_texts(user_lang)

        stats_text = f"{texts['stats_title']}\n\n"
        stats_text += f"🔸 {texts['stats_total']}：{stats['total_classifications']}\n"
        stats_text += f"🔸 {texts['stats_accuracy']}：{stats['accuracy_rate']:.1f}%\n"
        stats_text += f"🔸 {texts['stats_common']}：{stats['most_common_category']}\n"
        stats_text += f"🔸 {texts['stats_points']}：{stats['eco_points']}\n\n"
        stats_text += texts['stats_encourage']
        
        self.line_bot_api.reply_message(reply_token, TextMessage(text=stats_text))

    # ... (找到 _send_classification_result 函式的位置) ...

    def _create_result_flex_message(self, classification_result, waste_info, texts, user_lang):
        """建立精美的 Flex Message 分類結果卡片"""
        
        item_display_name = classification_result['item_name_en'] if user_lang == 'en' else classification_result['item_name_zh']
        category_display_text = f"{waste_info['category_name']} ({waste_info['category_name_zh']})"

        bubble = BubbleContainer(
            direction='ltr',
            header=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(text=texts['result_title'], weight='bold', size='xl', color='#1DB446')
                ]
            ),
            body=BoxComponent(
                layout='vertical',
                spacing='lg',
                contents=[
                    # 辨識物品
                    BoxComponent(
                        layout='horizontal',
                        contents=[
                            TextComponent(text=f"{texts['result_item']}:", size='sm', color='#555555', flex=4),
                            TextComponent(text=item_display_name, size='sm', color='#111111', align='end', flex=6, weight='bold')
                        ]
                    ),
                    # 類別
                    BoxComponent(
                        layout='horizontal',
                        contents=[
                            TextComponent(text=f"📂 {texts['result_category']}:", size='sm', color='#555555', flex=4),
                            TextComponent(text=category_display_text, size='sm', color='#111111', align='end', flex=6)
                        ]
                    ),
                    # 信心度
                    BoxComponent(
                        layout='horizontal',
                        contents=[
                            TextComponent(text=f"🎯 {texts['result_confidence']}:", size='sm', color='#555555', flex=4),
                            TextComponent(text=f"{classification_result['confidence']:.0%}", size='sm', color='#111111', align='end', flex=6)
                        ]
                    ),
                    SeparatorComponent(margin='md'),
                    # 處理方式
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        contents=[
                            TextComponent(text=f"♻️ {texts['result_method']}", weight='bold', size='md', margin='sm'),
                            TextComponent(text=waste_info['disposal_method'], wrap=True, size='sm', margin='md', color='#333333')
                        ]
                    ),
                    # 小提醒
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        contents=[
                            TextComponent(text=f"💡 {texts['result_tips']}", weight='bold', size='md', margin='sm'),
                            TextComponent(text=waste_info.get('tips', '-'), wrap=True, size='sm', margin='md', color='#333333')
                        ]
                    )
                ]
            )
        )
        return FlexSendMessage(alt_text=texts['result_title'], contents=bubble)

    def _send_classification_result(self, reply_token, classification_result, waste_info, texts, user_lang):
        """發送由 Flex Message 構成的分類結果"""
        flex_message = self._create_result_flex_message(classification_result, waste_info, texts, user_lang)
        self.line_bot_api.reply_message(reply_token, flex_message)





