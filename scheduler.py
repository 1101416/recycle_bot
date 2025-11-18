# 檔案: scheduler.py
# (此版本 v6.1 已修正時區為 Asia/Taipei)

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Dict
from config import Config
from recycle_db import RecycleDatabase
from garbage_truck_api import NewTaipeiTruckAPI
# (我們不需要 import zoneinfo 或 pytz，APScheduler 會自動處理 'Asia/Taipei' 字串)

logger = logging.getLogger(__name__)

class SchedulerManager:
    def __init__(self):
        # --- vvv 關鍵修改 vvv ---
        # 明確指定排程器使用「台灣時區」
        self.scheduler = BackgroundScheduler(timezone='Asia/Taipei')
        # --- ^^^ 關鍵修改 ^^^ ---
        
        self.recycle_db = RecycleDatabase()
        self.garbage_truck_api = NewTaipeiTruckAPI()
        self.is_running = False
        
        self._setup_jobs()
    
    def _setup_jobs(self):
        """設定排程任務"""
        try:
            # 每天凌晨 3:00 (現在會是 Asia/Taipei 時間) 更新垃圾車快取
            self.scheduler.add_job(
                func=self._update_garbage_truck_cache,
                trigger=CronTrigger(hour=3, minute=0), # <--- 這裡的 3 點已修正為台灣時間
                id='daily_truck_cache_update',
                name='每日垃圾車快取更新',
                replace_existing=True
            )
            
            logger.info("Scheduler jobs configured successfully (Data Update Only, Timezone: Asia/Taipei).")
            
        except Exception as e:
            logger.error(f"Error setting up scheduler jobs: {str(e)}")
    
    def start(self):
        try:
            if not self.is_running:
                self.scheduler.start()
                self.is_running = True
                logger.info("Scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
    
    def stop(self):
        try:
            if self.is_running:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("Scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
    
    def is_running(self) -> bool:
        return self.is_running and self.scheduler.running

    def _update_garbage_truck_cache(self):
        """(v4.0) 執行每日垃圾車快取更新"""
        try:
            logger.info("Scheduler Job: Starting daily garbage truck cache update (Asia/Taipei)...")
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
