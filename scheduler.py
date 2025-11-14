# 檔案: scheduler.py
# (此版本已移除所有使用者推播功能，只保留每日資料更新)

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Dict
from config import Config
from recycle_db import RecycleDatabase
from news_scraper import NewsScraper
from garbage_truck_api import NewTaipeiTruckAPI
# (移除了 linebot 相關的 import，因為不再需要推播)

logger = logging.getLogger(__name__)

class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.recycle_db = RecycleDatabase()
        self.news_scraper = NewsScraper()
        self.garbage_truck_api = NewTaipeiTruckAPI()
        # (移除了 self.line_bot_api)
        self.is_running = False
        
        # 設定排程任務
        self._setup_jobs()
    
    def _setup_jobs(self):
        """設定排程任務"""
        try:
            # --- 以下為保留的功能 ---
            
            # 每天凌晨 2:00 更新環保新聞
            self.scheduler.add_job(
                func=self._update_daily_news,
                trigger=CronTrigger(hour=2, minute=0),
                id='daily_news_update',
                name='每日新聞更新',
                replace_existing=True
            )
            
            # 每天凌晨 3:00 更新垃圾車快取
            self.scheduler.add_job(
                func=self._update_garbage_truck_cache,
                trigger=CronTrigger(hour=3, minute=0),
                id='daily_truck_cache_update',
                name='每日垃圾車快取更新',
                replace_existing=True
            )
            
            # --- 以上為保留的功能 ---
            
            # --- 以下為已移除的功能 ---
            # (移除了 _send_weekly_news)
            # (移除了 _send_weekly_tips)
            # (移除了 _send_weekly_quiz)
            # (移除了 _send_reminders)
            # --- 以上為已移除的功能 ---
            
            logger.info("Scheduler jobs configured successfully (Data Update Only).")
            
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
    
    # --- 以下為已移除的函式 ---
    # (_send_weekly_news, _send_weekly_tips, _send_weekly_quiz, _send_reminders)
    # (_get_active_users, _get_inactive_users)
    # (send_custom_message, send_broadcast_message)
    # --- 以上為已移除的函式 ---

    # --- 以下為保留的函式 ---
    
    def _update_daily_news(self):
        """更新每日環保新聞"""
        try:
            logger.info("Scheduler Job: Starting daily news update...")
            
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

    def _update_garbage_truck_cache(self):
        """(v4.0) 執行每日垃圾車快取更新"""
        try:
            logger.info("Scheduler Job: Starting daily garbage truck cache update...")
            success = self.garbage_truck_api.force_update_cache()
            if success:
                logger.info("Scheduler Job: Daily garbage truck cache update successful.")
            else:
                logger.error("Scheduler Job: Daily garbage truck cache update FAILED.")
        except Exception as e:
            logger.error(f"Error in daily garbage truck cache update job: {str(e)}")
    
    def get_job_status(self) -> Dict:
        """取得排程任務狀態 (保留給管理後台使用)"""
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
    # --- 以上為保留的函式 ---
