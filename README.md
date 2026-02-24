# AI 智能垃圾分類 LINE Bot

一個基於人工智慧的 LINE Bot，可以透過拍照識別垃圾類型並提供正確的回收處理方式。

## 🌟 主要功能

### 📸 智能垃圾分類
- 拍照上傳垃圾圖片，AI 自動識別垃圾類型
- 支援塑膠、紙類、金屬、玻璃、廚餘、電池、電子產品等分類
- 提供詳細的回收處理步驟和環保小貼士

### 🌍 多語言支援
- 繁體中文、英文、日文、韓文
- 使用者可自由切換語言介面

### 📰 環保資訊推播
- 每週推播最新環保新聞
- 定期分享環保小貼士
- 垃圾分類小測驗

### 🗺️ 位置服務
- 查詢附近回收站位置
- 垃圾車時間查詢（整合政府開放資料）

### 📊 個人統計
- 分類記錄統計
- 環保積分系統
- 正確分類率追蹤

## 🛠️ 技術架構

### 前端介面
- **LINE Bot API**: 處理使用者互動
- **多媒體訊息**: 支援圖片、文字、位置訊息
- **快速回覆**: 提供便捷的操作選單

### 後端服務
- **Flask**: Web 框架
- **TensorFlow**: AI 影像分類模型
- **SQLite**: 資料庫儲存
- **APScheduler**: 定時任務排程

### AI 模型
- **MobileNetV2**: 預訓練影像分類模型
- **自定義分類層**: 針對垃圾分類優化
- **信心度評估**: 提供分類可信度

## 📁 專案結構

```
ai-waste-classification-bot/
├── main.py                 # Flask 主程式
├── line_handler.py         # LINE 訊息處理器
├── image_classifier.py     # 影像分類模組
├── recycle_db.py          # 回收資料庫模組
├── news_scraper.py        # 環保新聞爬蟲
├── scheduler.py           # 定時推播排程器
├── database.py            # 資料庫初始化腳本
├── config.py              # 設定檔
├── requirements.txt       # Python 依賴
├── Dockerfile            # Docker 配置
├── render.yaml           # Render 部署配置
└── README.md             # 說明文件
```

## 🚀 快速開始

### 環境需求
- Python 3.9+
- LINE Developer Account
- 至少 1GB RAM

### 1. 克隆專案
```bash
git clone <repository-url>
cd ai-waste-classification-bot
```

### 2. 安裝依賴
```bash
pip install -r requirements.txt
```

### 3. 設定環境變數
建立 `.env` 檔案：
```env
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
LINE_CHANNEL_SECRET=your_channel_secret
DATABASE_URL=sqlite:///database.db
EPA_API_KEY=your_epa_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
PUSH_MESSAGE_ENABLED=true
```

### 4. 初始化資料庫
```bash
python database.py
```

### 5. 啟動應用程式
```bash
python main.py
```

## 🔧 配置說明

### LINE Bot 設定
1. 前往 [LINE Developers Console](https://developers.line.biz/)
2. 建立新的 Provider 和 Channel
3. 取得 Channel Access Token 和 Channel Secret
4. 設定 Webhook URL: `https://your-domain.com/webhook`

### 環境變數說明
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Bot 存取權杖
- `LINE_CHANNEL_SECRET`: LINE Bot 密鑰
- `DATABASE_URL`: 資料庫連線字串
- `EPA_API_KEY`: 環保署 API 金鑰（選用）
- `GOOGLE_MAPS_API_KEY`: Google Maps API 金鑰（選用）
- `PUSH_MESSAGE_ENABLED`: 是否啟用推播功能

## 📱 使用方式

### 基本操作
1. 加入 LINE Bot 為好友
2. 輸入 `/start` 開始使用
3. 拍照上傳垃圾圖片進行分類
4. 查看分類結果和回收建議

### 文字指令
- `/start` - 開始使用
- `/help` - 查看幫助
- `/language` - 語言設定
- `/news` - 環保新聞
- `/stats` - 個人統計
- `/search [垃圾名稱]` - 搜尋特定垃圾

### 位置功能
- 傳送位置資訊可查詢附近回收站
- 獲取垃圾車經過時間

## 🚀 部署指南

### Render 部署
1. 將程式碼推送到 GitHub
2. 在 Render 建立新的 Web Service
3. 連接 GitHub 儲存庫
4. 設定環境變數
5. 部署完成後設定 LINE Webhook URL

### Docker 部署
```bash
# 建構映像
docker build -t ai-waste-bot .

# 執行容器
docker run -p 5000:5000 \
  -e LINE_CHANNEL_ACCESS_TOKEN=your_token \
  -e LINE_CHANNEL_SECRET=your_secret \
  ai-waste-bot
```

### Heroku 部署
1. 安裝 Heroku CLI
2. 建立 Heroku 應用程式
3. 設定環境變數
4. 部署程式碼

## 🔍 API 端點

### Webhook 端點
- `POST /webhook` - LINE Bot Webhook

### 健康檢查
- `GET /` - 首頁
- `GET /health` - 健康檢查
- `GET /test` - 測試端點

## 📊 資料庫結構

### 主要表格
- `users` - 使用者資訊
- `classifications` - 分類記錄
- `waste_info` - 垃圾分類資訊
- `news` - 環保新聞
- `recycling_stations` - 回收站資訊

## 🤖 AI 模型訓練

### 準備訓練資料
1. 收集各類垃圾圖片
2. 標註正確分類
3. 資料預處理和增強

### 訓練模型
```python
from image_classifier import ImageClassifier

classifier = ImageClassifier()
history = classifier.train_model(training_data, validation_data)
```

### 模型評估
```python
results = classifier.evaluate_model(test_data)
print(f"Accuracy: {results['accuracy']:.2f}")
```

## 🔧 開發指南

### 新增垃圾分類
1. 在 `config.py` 中新增分類
2. 在 `database.py` 中新增預設資料
3. 重新訓練 AI 模型

### 新增語言支援
1. 在 `config.py` 中新增語言
2. 在 `line_handler.py` 中新增對應文字
3. 在 `news_scraper.py` 中新增新聞來源

### 自定義推播內容
1. 修改 `scheduler.py` 中的推播邏輯
2. 調整排程時間
3. 新增推播內容類型

## 🐛 故障排除

### 常見問題
1. **模型載入失敗**: 檢查模型檔案路徑
2. **資料庫連線錯誤**: 確認資料庫檔案權限
3. **LINE Webhook 驗證失敗**: 檢查 Channel Secret
4. **推播訊息失敗**: 確認 Channel Access Token

### 日誌查看
```bash
# 查看應用程式日誌
tail -f logs/app.log

# 查看錯誤日誌
grep "ERROR" logs/app.log
```

## 📈 效能優化

### 模型優化
- 使用 TensorFlow Lite 減少記憶體使用
- 模型量化降低檔案大小
- 快取機制提升回應速度

### 資料庫優化
- 建立適當的索引
- 定期清理舊資料
- 使用連線池

### 快取策略
- Redis 快取常用資料
- CDN 加速靜態資源
- 圖片壓縮優化

## 🤝 貢獻指南

1. Fork 專案
2. 建立功能分支
3. 提交變更
4. 發起 Pull Request

## 📄 授權條款

本專案採用 MIT 授權條款。

## 📞 聯絡資訊

如有問題或建議，請透過以下方式聯絡：
- 建立 Issue
- 發送 Email
- LINE 官方帳號

**讓我們一起為環保盡一份心力！🌱♻️**

