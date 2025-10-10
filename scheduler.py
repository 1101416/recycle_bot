import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from typing import List, Dict
from config import Config
from recycle_db import RecycleDatabase
from news_scraper import NewsScraper
from line_handler import LineMessageHandler
from linebot import LineBotApi
from linebot.models import TextMessage, PushMessage

logger = logging.getLogger(__name__)

class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.recycle_db = RecycleDatabase()
        self.news_scraper = NewsScraper()
        self.line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
        self.is_running = False
        
        # 設定排程任務
        self._setup_jobs()
    
    def _setup_jobs(self):
        """設定排程任務"""
        try:
            # 每週一早上 9:00 推播環保新聞
            self.scheduler.add_job(
                func=self._send_weekly_news,
                trigger=CronTrigger(day_of_week=0, hour=9, minute=0),
                id='weekly_news',
                name='每週環保新聞推播',
                replace_existing=True
            )
            
            # 每週三下午 2:00 推播環保小貼士
            self.scheduler.add_job(
                func=self._send_weekly_tips,
                trigger=CronTrigger(day_of_week=2, hour=14, minute=0),
                id='weekly_tips',
                name='每週環保小貼士',
                replace_existing=True
            )
            
            # 每週五晚上 7:00 推播垃圾分類小測驗
            self.scheduler.add_job(
                func=self._send_weekly_quiz,
                trigger=CronTrigger(day_of_week=4, hour=19, minute=0),
                id='weekly_quiz',
                name='每週垃圾分類小測驗',
                replace_existing=True
            )
            
            # 每天凌晨 2:00 更新環保新聞
            self.scheduler.add_job(
                func=self._update_daily_news,
                trigger=CronTrigger(hour=2, minute=0),
                id='daily_news_update',
                name='每日新聞更新',
                replace_existing=True
            )
            
            # 每小時檢查並發送提醒
            self.scheduler.add_job(
                func=self._send_reminders,
                trigger=IntervalTrigger(hours=1),
                id='hourly_reminders',
                name='每小時提醒檢查',
                replace_existing=True
            )
            
            logger.info("Scheduler jobs configured successfully")
            
        except Exception as e:
            logger.error(f"Error setting up scheduler jobs: {str(e)}")
    
    def start(self):
        """啟動排程器"""
        try:
            if not self.is_running:
                self.scheduler.start()
                self.is_running = True
                logger.info("Scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
    
    def stop(self):
        """停止排程器"""
        try:
            if self.is_running:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("Scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
    
    def is_running(self) -> bool:
        """檢查排程器是否運行中"""
        return self.is_running and self.scheduler.running
    
    def _send_weekly_news(self):
        """發送每週環保新聞"""
        try:
            logger.info("Sending weekly news...")
            
            # 取得所有活躍使用者
            active_users = self._get_active_users()
            
            for user in active_users:
                try:
                    user_lang = user.get('language', 'zh-TW')
                    
                    # 取得最新環保新聞
                    news = self.news_scraper.get_latest_news(user_lang)
                    
                    if news:
                        # 儲存到資料庫
                        self.recycle_db.add_news(
                            news['title'],
                            news['summary'],
                            news['url'],
                            user_lang
                        )
                        
                        # 發送推播訊息
                        message_text = f"📰 本週環保新聞\n\n{news['title']}\n\n{news['summary']}\n\n🔗 詳細內容：{news['url']}"
                        
                        self.line_bot_api.push_message(
                            user['user_id'],
                            TextMessage(text=message_text)
                        )
                        
                        logger.info(f"Weekly news sent to user {user['user_id']}")
                    
                except Exception as e:
                    logger.error(f"Error sending weekly news to user {user['user_id']}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in weekly news job: {str(e)}")
    
    def _send_weekly_tips(self):
        """發送每週環保小貼士"""
        try:
            logger.info("Sending weekly tips...")
            
            active_users = self._get_active_users()
            
            for user in active_users:
                try:
                    user_lang = user.get('language', 'zh-TW')
                    
                    # 取得環保小貼士
                    tips = self.news_scraper.get_environmental_tips(user_lang)
                    
                    if tips:
                        # 隨機選擇一個小貼士
                        import random
                        selected_tip = random.choice(tips)
                        
                        message_text = f"💡 本週環保小貼士\n\n{selected_tip}\n\n🌱 讓我們一起為地球盡一份心力！"
                        
                        self.line_bot_api.push_message(
                            user['user_id'],
                            TextMessage(text=message_text)
                        )
                        
                        logger.info(f"Weekly tip sent to user {user['user_id']}")
                    
                except Exception as e:
                    logger.error(f"Error sending weekly tip to user {user['user_id']}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in weekly tips job: {str(e)}")
    
    def _send_weekly_quiz(self):
        """發送每週垃圾分類小測驗"""
        try:
            logger.info("Sending weekly quiz...")
            
            active_users = self._get_active_users()
            
            # 測驗題目
            quiz_questions = {
                'zh-TW': [
                    {
                        'question': '塑膠瓶回收前需要做什麼？',
                        'options': ['A. 直接丟棄', 'B. 清洗後壓扁', 'C. 保持原樣'],
                        'answer': 'B',
                        'explanation': '塑膠瓶需要清洗乾淨後壓扁，才能投入回收桶。'
                    },
                    {
                        'question': '以下哪種物品不能回收？',
                        'options': ['A. 報紙', 'B. 衛生紙', 'C. 紙箱'],
                        'answer': 'B',
                        'explanation': '衛生紙、面紙等用過的紙類不能回收，需當一般垃圾處理。'
                    },
                    {
                        'question': '電池應該如何處理？',
                        'options': ['A. 投入一般垃圾', 'B. 投入回收桶', 'C. 投入電池回收桶'],
                        'answer': 'C',
                        'explanation': '電池含有重金屬，需要特別回收處理，不可投入一般垃圾。'
                    }
                ],
                'en': [
                    {
                        'question': 'What should you do with plastic bottles before recycling?',
                        'options': ['A. Throw away directly', 'B. Clean and flatten', 'C. Keep as is'],
                        'answer': 'B',
                        'explanation': 'Plastic bottles should be cleaned and flattened before recycling.'
                    }
                ]
            }
            
            for user in active_users:
                try:
                    user_lang = user.get('language', 'zh-TW')
                    questions = quiz_questions.get(user_lang, quiz_questions['zh-TW'])
                    
                    if questions:
                        import random
                        selected_question = random.choice(questions)
                        
                        message_text = f"🧠 本週垃圾分類小測驗\n\n{selected_question['question']}\n\n"
                        for option in selected_question['options']:
                            message_text += f"{option}\n"
                        message_text += f"\n💡 答案：{selected_question['answer']}\n"
                        message_text += f"📝 說明：{selected_question['explanation']}"
                        
                        self.line_bot_api.push_message(
                            user['user_id'],
                            TextMessage(text=message_text)
                        )
                        
                        logger.info(f"Weekly quiz sent to user {user['user_id']}")
                    
                except Exception as e:
                    logger.error(f"Error sending weekly quiz to user {user['user_id']}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in weekly quiz job: {str(e)}")
    
    def _update_daily_news(self):
        """更新每日環保新聞"""
        try:
            logger.info("Updating daily news...")
            
            # 為每種支援的語言更新新聞
            for language in Config.SUPPORTED_LANGUAGES.keys():
                try:
                    news = self.news_scraper.get_latest_news(language, limit=3)
                    if news:
                        # 儲存到資料庫
                        self.recycle_db.add_news(
                            news['title'],
                            news['summary'],
                            news['url'],
                            language
                        )
                        logger.info(f"Daily news updated for {language}")
                    
                except Exception as e:
                    logger.error(f"Error updating daily news for {language}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in daily news update job: {str(e)}")
    
    def _send_reminders(self):
        """發送提醒訊息"""
        try:
            # 檢查是否有需要發送提醒的使用者
            # 例如：長時間未使用的使用者
            inactive_users = self._get_inactive_users(days=7)
            
            for user in inactive_users:
                try:
                    user_lang = user.get('language', 'zh-TW')
                    
                    reminder_messages = {
                        'zh-TW': "🌱 好久不見！記得做好垃圾分類，保護我們的地球環境。",
                        'en': "🌱 Long time no see! Remember to sort your waste properly to protect our environment.",
                        'ja': "🌱 お久しぶりです！ゴミ分別を忘れずに、地球環境を守りましょう。",
                        'ko': "🌱 오랜만이에요! 쓰레기 분리수거를 잊지 말고 지구 환경을 보호해요."
                    }
                    
                    message_text = reminder_messages.get(user_lang, reminder_messages['zh-TW'])
                    
                    self.line_bot_api.push_message(
                        user['user_id'],
                        TextMessage(text=message_text)
                    )
                    
                    logger.info(f"Reminder sent to inactive user {user['user_id']}")
                    
                except Exception as e:
                    logger.error(f"Error sending reminder to user {user['user_id']}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in reminders job: {str(e)}")
    
    def _get_active_users(self, days: int = 30) -> List[Dict]:
        """取得活躍使用者列表"""
        try:
            with self.recycle_db as conn:
                cursor = conn.cursor()
                
                # 取得最近 N 天內有活動的使用者
                cutoff_date = datetime.now() - timedelta(days=days)
                
                cursor.execute('''
                    SELECT user_id, language, last_active, eco_points
                    FROM users 
                    WHERE last_active >= ?
                    ORDER BY last_active DESC
                ''', (cutoff_date,))
                
                users = cursor.fetchall()
                
                return [
                    {
                        'user_id': user[0],
                        'language': user[1],
                        'last_active': user[2],
                        'eco_points': user[3]
                    }
                    for user in users
                ]
                
        except Exception as e:
            logger.error(f"Error getting active users: {str(e)}")
            return []
    
    def _get_inactive_users(self, days: int = 7) -> List[Dict]:
        """取得非活躍使用者列表"""
        try:
            with self.recycle_db as conn:
                cursor = conn.cursor()
                
                # 取得超過 N 天未活動的使用者
                cutoff_date = datetime.now() - timedelta(days=days)
                
                cursor.execute('''
                    SELECT user_id, language, last_active, eco_points
                    FROM users 
                    WHERE last_active < ?
                    ORDER BY last_active ASC
                ''', (cutoff_date,))
                
                users = cursor.fetchall()
                
                return [
                    {
                        'user_id': user[0],
                        'language': user[1],
                        'last_active': user[2],
                        'eco_points': user[3]
                    }
                    for user in users
                ]
                
        except Exception as e:
            logger.error(f"Error getting inactive users: {str(e)}")
            return []
    
    def send_custom_message(self, user_id: str, message: str) -> bool:
        """發送自定義訊息給特定使用者"""
        try:
            self.line_bot_api.push_message(
                user_id,
                TextMessage(text=message)
            )
            logger.info(f"Custom message sent to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending custom message to user {user_id}: {str(e)}")
            return False
    
    def send_broadcast_message(self, message: str, language: str = None) -> int:
        """發送廣播訊息給所有使用者或特定語言的使用者"""
        try:
            active_users = self._get_active_users()
            sent_count = 0
            
            for user in active_users:
                try:
                    # 如果指定了語言，只發送給該語言的使用者
                    if language and user.get('language') != language:
                        continue
                    
                    self.line_bot_api.push_message(
                        user['user_id'],
                        TextMessage(text=message)
                    )
                    sent_count += 1
                    
                except Exception as e:
                    logger.error(f"Error sending broadcast to user {user['user_id']}: {str(e)}")
                    continue
            
            logger.info(f"Broadcast message sent to {sent_count} users")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error in broadcast message: {str(e)}")
            return 0
    
    def get_job_status(self) -> Dict:
        """取得排程任務狀態"""
        try:
            jobs = self.scheduler.get_jobs()
            
            job_status = []
            for job in jobs:
                job_status.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                })
            
            return {
                'scheduler_running': self.is_running,
                'total_jobs': len(jobs),
                'jobs': job_status
            }
            
        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
            return {
                'scheduler_running': False,
                'total_jobs': 0,
                'jobs': []
            }
