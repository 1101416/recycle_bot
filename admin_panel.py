from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from config import Config
from recycle_db import RecycleDatabase
from scheduler import SchedulerManager

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 建立 Flask 應用程式
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# 設定登入管理
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 初始化資料庫和排程器
db = RecycleDatabase()
scheduler = SchedulerManager()

class AdminUser(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    """載入使用者"""
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, email FROM admin_users WHERE id = ?', (user_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                return AdminUser(user_data[0], user_data[1], user_data[2])
    except Exception as e:
        logger.error(f"載入使用者失敗: {str(e)}")
    return None

def init_admin_tables():
    """初始化管理員表格"""
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            
            # 管理員表格
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # 系統日誌表格
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    module TEXT,
                    user_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 檢查是否有管理員
            cursor.execute('SELECT COUNT(*) FROM admin_users')
            count = cursor.fetchone()[0]
            
            if count == 0:
                # 建立預設管理員
                password_hash = generate_password_hash('admin123')
                cursor.execute('''
                    INSERT INTO admin_users (username, email, password_hash)
                    VALUES (?, ?, ?)
                ''', ('admin', 'admin@example.com', password_hash))
                
                logger.info("預設管理員已建立: admin / admin123")
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"初始化管理員表格失敗: {str(e)}")

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    """管理員登入"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            with sqlite3.connect('database.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email, password_hash FROM admin_users 
                    WHERE username = ? AND is_active = 1
                ''', (username,))
                user_data = cursor.fetchone()
                
                if user_data and check_password_hash(user_data[3], password):
                    user = AdminUser(user_data[0], user_data[1], user_data[2])
                    login_user(user)
                    
                    # 更新最後登入時間
                    cursor.execute('''
                        UPDATE admin_users SET last_login = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    ''', (user_data[0],))
                    conn.commit()
                    
                    flash('登入成功！', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('使用者名稱或密碼錯誤！', 'error')
        except Exception as e:
            logger.error(f"登入失敗: {str(e)}")
            flash('登入時發生錯誤！', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
@login_required
def logout():
    """管理員登出"""
    logout_user()
    flash('已成功登出！', 'info')
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def dashboard():
    """管理後台首頁"""
    try:
        # 取得統計資料
        stats = db.get_database_stats()
        
        # 取得最近活動
        recent_classifications = get_recent_classifications(10)
        
        # 取得系統狀態
        system_status = {
            'scheduler_running': scheduler.is_running(),
            'database_connected': True,
            'model_loaded': os.path.exists(Config.MODEL_PATH)
        }
        
        return render_template('admin/dashboard.html', 
                             stats=stats, 
                             recent_classifications=recent_classifications,
                             system_status=system_status)
    
    except Exception as e:
        logger.error(f"載入儀表板失敗: {str(e)}")
        flash('載入儀表板時發生錯誤！', 'error')
        return render_template('admin/dashboard.html', 
                             stats={}, 
                             recent_classifications=[],
                             system_status={})

@app.route('/admin/users')
@login_required
def users():
    """使用者管理"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # 取得使用者列表
        users_data = get_users_list(page, per_page)
        
        return render_template('admin/users.html', users=users_data)
    
    except Exception as e:
        logger.error(f"載入使用者列表失敗: {str(e)}")
        flash('載入使用者列表時發生錯誤！', 'error')
        return render_template('admin/users.html', users=[])

@app.route('/admin/classifications')
@login_required
def classifications():
    """分類記錄管理"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # 取得分類記錄
        classifications_data = get_classifications_list(page, per_page)
        
        return render_template('admin/classifications.html', 
                             classifications=classifications_data)
    
    except Exception as e:
        logger.error(f"載入分類記錄失敗: {str(e)}")
        flash('載入分類記錄時發生錯誤！', 'error')
        return render_template('admin/classifications.html', classifications=[])

@app.route('/admin/waste-info')
@login_required
def waste_info():
    """垃圾資訊管理"""
    try:
        # 取得垃圾資訊
        waste_info_data = get_waste_info_list()
        
        return render_template('admin/waste_info.html', waste_info=waste_info_data)
    
    except Exception as e:
        logger.error(f"載入垃圾資訊失敗: {str(e)}")
        flash('載入垃圾資訊時發生錯誤！', 'error')
        return render_template('admin/waste_info.html', waste_info=[])

@app.route('/admin/news')
@login_required
def news():
    """新聞管理"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # 取得新聞列表
        news_data = get_news_list(page, per_page)
        
        return render_template('admin/news.html', news=news_data)
    
    except Exception as e:
        logger.error(f"載入新聞列表失敗: {str(e)}")
        flash('載入新聞列表時發生錯誤！', 'error')
        return render_template('admin/news.html', news=[])

@app.route('/admin/scheduler')
@login_required
def scheduler_management():
    """排程器管理"""
    try:
        # 取得排程器狀態
        job_status = scheduler.get_job_status()
        
        return render_template('admin/scheduler.html', job_status=job_status)
    
    except Exception as e:
        logger.error(f"載入排程器狀態失敗: {str(e)}")
        flash('載入排程器狀態時發生錯誤！', 'error')
        return render_template('admin/scheduler.html', job_status={})

@app.route('/admin/api/stats')
@login_required
def api_stats():
    """API: 取得統計資料"""
    try:
        stats = db.get_database_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"取得統計資料失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/users')
@login_required
def api_users():
    """API: 取得使用者列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        users_data = get_users_list(page, per_page)
        return jsonify(users_data)
    except Exception as e:
        logger.error(f"取得使用者列表失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/classifications')
@login_required
def api_classifications():
    """API: 取得分類記錄"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        classifications_data = get_classifications_list(page, per_page)
        return jsonify(classifications_data)
    except Exception as e:
        logger.error(f"取得分類記錄失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/send-message', methods=['POST'])
@login_required
def api_send_message():
    """API: 發送訊息"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        message = data.get('message')
        
        if not user_id or not message:
            return jsonify({'error': '缺少必要參數'}), 400
        
        success = scheduler.send_custom_message(user_id, message)
        
        if success:
            return jsonify({'success': True, 'message': '訊息發送成功'})
        else:
            return jsonify({'error': '訊息發送失敗'}), 500
    
    except Exception as e:
        logger.error(f"發送訊息失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    """API: 廣播訊息"""
    try:
        data = request.get_json()
        message = data.get('message')
        language = data.get('language')
        
        if not message:
            return jsonify({'error': '缺少訊息內容'}), 400
        
        sent_count = scheduler.send_broadcast_message(message, language)
        
        return jsonify({'success': True, 'sent_count': sent_count})
    
    except Exception as e:
        logger.error(f"廣播訊息失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_recent_classifications(limit: int = 10) -> List[Dict]:
    """取得最近的分類記錄"""
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.id, c.user_id, c.category, c.confidence, c.created_at,
                       u.language, u.eco_points
                FROM classifications c
                LEFT JOIN users u ON c.user_id = u.user_id
                ORDER BY c.created_at DESC
                LIMIT ?
            ''', (limit,))
            
            results = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'user_id': row[1],
                    'category': row[2],
                    'confidence': row[3],
                    'created_at': row[4],
                    'language': row[5],
                    'eco_points': row[6]
                }
                for row in results
            ]
    
    except Exception as e:
        logger.error(f"取得最近分類記錄失敗: {str(e)}")
        return []

def get_users_list(page: int, per_page: int) -> Dict:
    """取得使用者列表"""
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            
            # 計算總數
            cursor.execute('SELECT COUNT(*) FROM users')
            total = cursor.fetchone()[0]
            
            # 計算偏移量
            offset = (page - 1) * per_page
            
            # 取得使用者資料
            cursor.execute('''
                SELECT u.user_id, u.language, u.created_at, u.last_active, u.eco_points,
                       COUNT(c.id) as classification_count
                FROM users u
                LEFT JOIN classifications c ON u.user_id = c.user_id
                GROUP BY u.user_id
                ORDER BY u.last_active DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            users = cursor.fetchall()
            
            return {
                'users': [
                    {
                        'user_id': user[0],
                        'language': user[1],
                        'created_at': user[2],
                        'last_active': user[3],
                        'eco_points': user[4],
                        'classification_count': user[5]
                    }
                    for user in users
                ],
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
    
    except Exception as e:
        logger.error(f"取得使用者列表失敗: {str(e)}")
        return {'users': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}

def get_classifications_list(page: int, per_page: int) -> Dict:
    """取得分類記錄列表"""
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            
            # 計算總數
            cursor.execute('SELECT COUNT(*) FROM classifications')
            total = cursor.fetchone()[0]
            
            # 計算偏移量
            offset = (page - 1) * per_page
            
            # 取得分類記錄
            cursor.execute('''
                SELECT c.id, c.user_id, c.category, c.confidence, c.is_correct,
                       c.feedback, c.created_at, u.language
                FROM classifications c
                LEFT JOIN users u ON c.user_id = u.user_id
                ORDER BY c.created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            classifications = cursor.fetchall()
            
            return {
                'classifications': [
                    {
                        'id': cls[0],
                        'user_id': cls[1],
                        'category': cls[2],
                        'confidence': cls[3],
                        'is_correct': cls[4],
                        'feedback': cls[5],
                        'created_at': cls[6],
                        'language': cls[7]
                    }
                    for cls in classifications
                ],
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
    
    except Exception as e:
        logger.error(f"取得分類記錄列表失敗: {str(e)}")
        return {'classifications': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}

def get_waste_info_list() -> List[Dict]:
    """取得垃圾資訊列表"""
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT category, name, disposal_method, tips, language, created_at
                FROM waste_info
                ORDER BY category, language, name
            ''')
            
            results = cursor.fetchall()
            
            return [
                {
                    'category': row[0],
                    'name': row[1],
                    'disposal_method': row[2],
                    'tips': row[3],
                    'language': row[4],
                    'created_at': row[5]
                }
                for row in results
            ]
    
    except Exception as e:
        logger.error(f"取得垃圾資訊列表失敗: {str(e)}")
        return []

def get_news_list(page: int, per_page: int) -> Dict:
    """取得新聞列表"""
    try:
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            
            # 計算總數
            cursor.execute('SELECT COUNT(*) FROM news')
            total = cursor.fetchone()[0]
            
            # 計算偏移量
            offset = (page - 1) * per_page
            
            # 取得新聞
            cursor.execute('''
                SELECT id, title, content, url, language, published_at, created_at
                FROM news
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            news = cursor.fetchall()
            
            return {
                'news': [
                    {
                        'id': item[0],
                        'title': item[1],
                        'content': item[2],
                        'url': item[3],
                        'language': item[4],
                        'published_at': item[5],
                        'created_at': item[6]
                    }
                    for item in news
                ],
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
    
    except Exception as e:
        logger.error(f"取得新聞列表失敗: {str(e)}")
        return {'news': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}

if __name__ == '__main__':
    # 初始化管理員表格
    init_admin_tables()
    
    # 啟動應用程式
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
