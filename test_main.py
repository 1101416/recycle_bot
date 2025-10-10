import unittest
import tempfile
import os
import sqlite3
from unittest.mock import Mock, patch
import numpy as np
from PIL import Image

# 匯入專案模組
from config import Config
from recycle_db import RecycleDatabase
from image_classifier import ImageClassifier
from news_scraper import NewsScraper
from scheduler import SchedulerManager

class TestRecycleDatabase(unittest.TestCase):
    """測試回收資料庫模組"""
    
    def setUp(self):
        """設定測試環境"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db = RecycleDatabase(self.temp_db.name)
    
    def tearDown(self):
        """清理測試環境"""
        os.unlink(self.temp_db.name)
    
    def test_init_database(self):
        """測試資料庫初始化"""
        # 檢查表格是否建立
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = ['users', 'classifications', 'waste_info', 'news', 'recycling_stations']
            for table in expected_tables:
                self.assertIn(table, tables)
    
    def test_user_operations(self):
        """測試使用者操作"""
        user_id = "test_user_123"
        
        # 測試創建使用者
        user = self.db.get_or_create_user(user_id, 'zh-TW')
        self.assertEqual(user['user_id'], user_id)
        self.assertEqual(user['language'], 'zh-TW')
        
        # 測試取得使用者語言
        language = self.db.get_user_language(user_id)
        self.assertEqual(language, 'zh-TW')
        
        # 測試更新語言
        success = self.db.update_user_language(user_id, 'en')
        self.assertTrue(success)
        
        language = self.db.get_user_language(user_id)
        self.assertEqual(language, 'en')
    
    def test_classification_recording(self):
        """測試分類記錄"""
        user_id = "test_user_123"
        
        # 記錄分類
        success = self.db.record_classification(
            user_id, 'plastic', 0.85, None, True, None
        )
        self.assertTrue(success)
        
        # 檢查統計
        stats = self.db.get_user_stats(user_id)
        self.assertEqual(stats['total_classifications'], 1)
        self.assertEqual(stats['accuracy_rate'], 100.0)
    
    def test_waste_info(self):
        """測試垃圾資訊查詢"""
        # 測試取得垃圾資訊
        waste_info = self.db.get_waste_info('plastic', 'zh-TW')
        self.assertIsNotNone(waste_info)
        self.assertEqual(waste_info['category'], 'plastic')
        
        # 測試搜尋垃圾
        search_result = self.db.search_waste_by_name('塑膠瓶', 'zh-TW')
        self.assertIsNotNone(search_result)

class TestImageClassifier(unittest.TestCase):
    """測試影像分類模組"""
    
    def setUp(self):
        """設定測試環境"""
        self.classifier = ImageClassifier()
    
    def test_model_loading(self):
        """測試模型載入"""
        self.assertIsNotNone(self.classifier.model)
        self.assertIsNotNone(self.classifier.class_names)
    
    def test_image_preprocessing(self):
        """測試圖片預處理"""
        # 建立測試圖片
        test_image = Image.new('RGB', (100, 100), color='red')
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            test_image.save(temp_file.name)
            temp_file_path = temp_file.name
        
        try:
            processed = self.classifier.preprocess_image(temp_file_path)
            self.assertIsNotNone(processed)
            self.assertEqual(processed.shape, (1, *Config.IMAGE_SIZE, 3))
        finally:
            os.unlink(temp_file_path)
    
    def test_classification(self):
        """測試分類功能"""
        # 建立測試圖片
        test_image = Image.new('RGB', (100, 100), color='red')
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            test_image.save(temp_file.name)
            temp_file_path = temp_file.name
        
        try:
            result = self.classifier.classify_image(temp_file_path)
            # 由於是隨機圖片，可能無法正確分類，但應該有結果
            if result:
                self.assertIn('category', result)
                self.assertIn('confidence', result)
                self.assertIn(result['category'], self.classifier.class_names)
        finally:
            os.unlink(temp_file_path)

class TestNewsScraper(unittest.TestCase):
    """測試新聞爬蟲模組"""
    
    def setUp(self):
        """設定測試環境"""
        self.scraper = NewsScraper()
    
    def test_default_news(self):
        """測試預設新聞"""
        news = self.scraper._get_default_news('zh-TW')
        self.assertIsNotNone(news)
        self.assertIn('title', news)
        self.assertIn('summary', news)
        self.assertIn('url', news)
    
    def test_environmental_tips(self):
        """測試環保小貼士"""
        tips = self.scraper.get_environmental_tips('zh-TW')
        self.assertIsInstance(tips, list)
        self.assertGreater(len(tips), 0)
    
    def test_recycling_guide(self):
        """測試回收指南"""
        guide = self.scraper.get_recycling_guide('plastic', 'zh-TW')
        self.assertIsNotNone(guide)
        self.assertIn('title', guide)
        self.assertIn('steps', guide)

class TestSchedulerManager(unittest.TestCase):
    """測試排程器管理"""
    
    def setUp(self):
        """設定測試環境"""
        self.scheduler = SchedulerManager()
    
    def test_scheduler_initialization(self):
        """測試排程器初始化"""
        self.assertIsNotNone(self.scheduler.scheduler)
        self.assertIsNotNone(self.scheduler.recycle_db)
        self.assertIsNotNone(self.scheduler.news_scraper)
    
    def test_job_status(self):
        """測試任務狀態"""
        status = self.scheduler.get_job_status()
        self.assertIn('scheduler_running', status)
        self.assertIn('total_jobs', status)
        self.assertIn('jobs', status)

class TestConfig(unittest.TestCase):
    """測試設定模組"""
    
    def test_config_values(self):
        """測試設定值"""
        self.assertIsNotNone(Config.SUPPORTED_LANGUAGES)
        self.assertIsNotNone(Config.WASTE_CATEGORIES)
        self.assertGreater(len(Config.SUPPORTED_LANGUAGES), 0)
        self.assertGreater(len(Config.WASTE_CATEGORIES), 0)
    
    def test_language_support(self):
        """測試語言支援"""
        expected_languages = ['zh-TW', 'en', 'ja', 'ko']
        for lang in expected_languages:
            self.assertIn(lang, Config.SUPPORTED_LANGUAGES)
    
    def test_waste_categories(self):
        """測試垃圾分類"""
        expected_categories = ['plastic', 'paper', 'metal', 'glass', 'organic', 'battery', 'electronics', 'other']
        for category in expected_categories:
            self.assertIn(category, Config.WASTE_CATEGORIES)

class TestIntegration(unittest.TestCase):
    """整合測試"""
    
    def setUp(self):
        """設定測試環境"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db = RecycleDatabase(self.temp_db.name)
        self.classifier = ImageClassifier()
        self.scraper = NewsScraper()
    
    def tearDown(self):
        """清理測試環境"""
        os.unlink(self.temp_db.name)
    
    def test_end_to_end_classification(self):
        """測試端到端分類流程"""
        user_id = "integration_test_user"
        
        # 1. 創建使用者
        user = self.db.get_or_create_user(user_id, 'zh-TW')
        self.assertEqual(user['user_id'], user_id)
        
        # 2. 建立測試圖片
        test_image = Image.new('RGB', (100, 100), color='blue')
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            test_image.save(temp_file.name)
            temp_file_path = temp_file.name
        
        try:
            # 3. 進行分類
            result = self.classifier.classify_image(temp_file_path)
            
            if result:
                # 4. 記錄分類結果
                success = self.db.record_classification(
                    user_id, result['category'], result['confidence']
                )
                self.assertTrue(success)
                
                # 5. 取得垃圾資訊
                waste_info = self.db.get_waste_info(result['category'], 'zh-TW')
                self.assertIsNotNone(waste_info)
                
                # 6. 檢查統計
                stats = self.db.get_user_stats(user_id)
                self.assertEqual(stats['total_classifications'], 1)
        finally:
            os.unlink(temp_file_path)

def run_tests():
    """執行所有測試"""
    # 建立測試套件
    test_suite = unittest.TestSuite()
    
    # 添加測試類別
    test_classes = [
        TestRecycleDatabase,
        TestImageClassifier,
        TestNewsScraper,
        TestSchedulerManager,
        TestConfig,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 執行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
