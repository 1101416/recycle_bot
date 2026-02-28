# AI 智能垃圾分類 LINE Bot - 專案完成總結

## 🎉 專案完成狀態

✅ **所有核心功能已完成實作！**

## 📁 專案檔案結構

```text
ai-waste-classification-bot/
├── 📄 核心應用程式檔案
│   ├── main.py                    # Flask 主程式
│   ├── line_handler.py           # LINE 訊息處理器
│   ├── image_classifier.py       # 整合 Gemini API 的影像與文字分類模組
│   ├── recycle_db.py            # 回收資料庫模組
│   ├── clothing_box_finder.py   # 舊衣回收箱 LBS 空間運算模組
│   ├── garbage_truck_api.py     # 垃圾車動態 API 模組
│   ├── news_scraper.py          # 環保新聞爬蟲
│   ├── scheduler.py             # 定時推播排程器
│   ├── database.py              # 資料庫初始化腳本
│   └── config.py                # 系統環境與分類設定檔
│
├── 📋 配置和部署檔案
│   ├── requirements.txt         # Python 依賴
│   ├── Dockerfile              # Docker 配置
│   ├── render.yaml             # Render 部署配置
│   ├── Procfile               # Heroku 部署配置
│   ├── runtime.txt            # Python 版本
│   ├── old_clothes_WITH_COORDS_full.csv # 舊衣回收箱座標資料庫
│   └── .dockerignore          # Docker 忽略檔案
│
└── 📚 文檔和說明
    ├── README.md              # 主要說明文件
    ├── API_DOCUMENTATION.md   # API 文檔
    ├── env_example.txt        # 環境變數範例
    └── PROJECT_SUMMARY.md     # 專案總結（本檔案）

```

## 🌟 已實作功能

### 💬 使用者介面層（LINE 互動介面）

* ✅ **多語言選擇**: 支援繁體中文與英文 (定義於 config.py)
* ✅ **多模態輸入**: 支援隨拍即查（圖片）與文字輸入描述，即時回傳分類建議與清潔指引。

### ⚙️ 核心功能層（分類與資料處理）

* ✅ **生成式 AI 分類引擎**: 整合 Google Gemini 2.5 Flash-Lite 模型，並導入針對台灣環保署規則的 Prompt Engineering。
* ✅ **回收知識資料庫**: SQLite 資料庫，包含完整垃圾資訊。
* ✅ **LBS 智慧清運**: 基於 Haversine Formula 計算，即時列出最近的「舊衣回收站」與「垃圾車」資訊。

### 🌱 擴充功能層（延伸與教育功能）

* ✅ **環保知識推播**: 定時推播環保新聞。
* ✅ **資料連結提供**: 整合政府開放資料與自動化爬蟲數據。

### ☁️ 後端架構層（Render + 程式架構）

* ✅ **Flask 主程式**: 完整的 Web 服務與 Webhook 驗證。
* ✅ **定時排程器**: APScheduler 背景自動化任務。

## 🔧 設定步驟

### 1. 環境變數設定

複製 `env_example.txt` 為 `.env` 並填入實際值：

```env
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
LINE_CHANNEL_SECRET=your_channel_secret
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=sqlite:///database.db
PUSH_MESSAGE_ENABLED=true

```

## 📊 功能特色

### 🤖 AI 智能分類 (Gemini 2.5 Flash-Lite)

* 支援高達 13 種分類判斷（包含廚餘、各類回收物、電子廢棄物、大型廢棄物、有害垃圾等）。
* 具備防呆機制，能自動辨識純聊天訊息或非實體物品（如螢幕截圖）。
* 依循台灣在地回收規則（如：衛生紙視為一般垃圾、複合材質判定邏輯）。

### 🌍 多語言支援

* 繁體中文（主要）
* 英文

### 📱 完整 LINE Bot 功能

* 文字指令與自然語言提問
* 圖片上傳辨識
* 位置服務 (LBS 尋找最近回收站)

### 🔔 智能推播

* 定時推播環保新聞與小貼士

## 🎯 專案成果

### 🌟 專案亮點

* **無伺服器 GPU 需求**: 透過 API 呼叫大型語言模型(LLM)，大幅降低部署成本。
* **高擴充性 Prompt 架構**: 垃圾分類規則可直接透過修改 `SYSTEM_PROMPT` 進行熱更新，無需重新訓練模型。
* **在地化 LBS 服務**: 結合自建的數千筆舊衣回收座標資料庫，提供精準導航。

```

```markdown
# AI 智能垃圾分類 LINE Bot

結合台灣高滲透率的 LINE 平台與生成式 AI 技術，打造低使用成本的個人化環保助理。透過圖文雙模態識別，解決民眾面對複雜回收規則的痛點，並提供最近的清運站點資訊。

## 🌟 主要功能

### 📸 智能垃圾分類 (Powered by Gemini)
- 支援影像與文字輸入，AI 自動辨識垃圾類型。
- 支援 13 種精細分類（塑膠、紙類、金屬、玻璃、廚餘、電子廢棄物、有害垃圾、大型家具等）。
- 內建台灣環保署最新回收規則邏輯（如區分紙類與不可回收之衛生紙/髒污紙容器）。

### 🌍 語言支援
- 繁體中文、英文
- 使用者可自由切換語言介面

### 📰 環保資訊推播
- 定期推播最新環保新聞與知識。

### 🗺️ 位置服務 (LBS)
- 傳送定位資訊，即時計算球面距離 (Haversine Formula)。
- 查詢半徑內最近的「舊衣回收箱」與「垃圾車」動態資訊。

## 🛠️ 技術架構

### 前端介面
- **LINE Messaging API**: 處理使用者文字、圖片、位置訊息與 Postback 互動。

### 後端服務
- **Python Flask**: 核心 Web 框架。
- **SQLite**: 資料庫儲存。
- **APScheduler**: 定時任務排程（新聞推播）。

### AI 與資料處理
- **Google Gemini API (2.5 Flash-Lite)**: 處理影像辨識與自然語言理解，取代傳統笨重的本地影像分類模型。
- **Prompt Engineering**: 建構專屬決策樹邏輯，提高判讀台灣在地回收規則準確率。
- **空間演算法**: 經緯度距離精算與排序。

## 🚀 快速開始

### 環境需求
- Python 3.9+
- LINE Developer Account
- Google AI Studio API Key (Gemini)

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
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=sqlite:///database.db
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

## 📱 使用方式

### 基本操作

1. 加入 LINE Bot 為好友。
2. 直接拍攝垃圾照片，或輸入文字（例如：「壞掉的鍵盤怎麼丟？」）。
3. 獲取詳細的分類結果與處理建議。

### 位置功能

* 在對話框中選擇「傳送位置資訊」，系統將自動回傳距離您最近的舊衣回收站點與垃圾車資訊。

## 🤖 AI 邏輯說明

本專案摒棄了傳統需要大量運算資源的 CNN 模型，改採 **Generative AI (Gemini 2.5 Flash-Lite)**。
透過在 `image_classifier.py` 中嚴格定義的 `SYSTEM_PROMPT`，AI 具備以下決策能力：

1. **防呆過濾**：自動辨識日常寒暄對話與非實體圖片（如螢幕截圖）。
2. **材質優先判定**：根據台灣回收指引，對複合材質或特殊物品（如電池、燈泡等有害垃圾）進行優先級攔截。
3. **模糊容錯**：對於無法確定的物品，給予「疑似」標籤並歸類為一般垃圾，避免錯誤回收污染回收線。

## 🤝 貢獻指南

1. Fork 專案
2. 建立功能分支
3. 提交變更
4. 發起 Pull Request

## 📄 授權條款

本專案採用 MIT 授權條款。
