# AI 智能垃圾分類 LINE Bot API 文檔

## 概述

本 API 文檔描述了 AI 智能垃圾分類 LINE Bot 的所有端點和功能。

## 基礎資訊

- **基礎 URL**: `https://your-domain.com`
- **API 版本**: v1.0.0
- **認證方式**: LINE Bot Channel Access Token
- **資料格式**: JSON

## 端點列表

### 1. Webhook 端點

#### POST /webhook
LINE Bot 的主要 webhook 端點，接收 LINE 平台的所有事件。

**請求標頭**:
```
Content-Type: application/json
X-Line-Signature: <簽名>
```

**請求體**:
```json
{
  "events": [
    {
      "type": "message",
      "replyToken": "replyToken",
      "source": {
        "userId": "userId",
        "type": "user"
      },
      "timestamp": 1234567890123,
      "message": {
        "type": "text",
        "text": "Hello"
      }
    }
  ]
}
```

**回應**:
```
200 OK
```

### 2. 健康檢查端點

#### GET /
應用程式首頁和基本健康檢查。

**回應**:
```json
{
  "message": "AI 智能垃圾分類 LINE Bot 運行中！",
  "status": "healthy",
  "version": "1.0.0"
}
```

#### GET /health
詳細的健康檢查端點。

**回應**:
```json
{
  "status": "healthy",
  "services": {
    "line_bot": "running",
    "database": "connected",
    "scheduler": "running"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### GET /test
測試端點。

**回應**:
```json
{
  "status": "success",
  "message": "AI 智能垃圾分類 LINE Bot 測試成功！",
  "version": "1.0.0"
}
```

## 管理後台 API

### 認證

管理後台 API 需要登入認證。請先透過 `/admin/login` 登入。

### 3. 統計資料 API

#### GET /admin/api/stats
取得系統統計資料。

**認證**: 需要登入

**回應**:
```json
{
  "total_users": 150,
  "total_classifications": 1250,
  "total_waste_info": 45,
  "total_news": 20,
  "total_stations": 8,
  "active_users_7days": 85,
  "classifications_today": 25
}
```

### 4. 使用者管理 API

#### GET /admin/api/users
取得使用者列表。

**認證**: 需要登入

**查詢參數**:
- `page` (int): 頁碼，預設 1
- `per_page` (int): 每頁數量，預設 20

**回應**:
```json
{
  "users": [
    {
      "user_id": "U1234567890abcdef",
      "language": "zh-TW",
      "created_at": "2024-01-01T00:00:00Z",
      "last_active": "2024-01-01T12:00:00Z",
      "eco_points": 15,
      "classification_count": 8
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 20,
  "total_pages": 8
}
```

### 5. 分類記錄 API

#### GET /admin/api/classifications
取得分類記錄列表。

**認證**: 需要登入

**查詢參數**:
- `page` (int): 頁碼，預設 1
- `per_page` (int): 每頁數量，預設 20

**回應**:
```json
{
  "classifications": [
    {
      "id": 1,
      "user_id": "U1234567890abcdef",
      "category": "plastic",
      "confidence": 0.95,
      "is_correct": true,
      "feedback": null,
      "created_at": "2024-01-01T12:00:00Z",
      "language": "zh-TW"
    }
  ],
  "total": 1250,
  "page": 1,
  "per_page": 20,
  "total_pages": 63
}
```

### 6. 訊息發送 API

#### POST /admin/api/send-message
發送訊息給特定使用者。

**認證**: 需要登入

**請求體**:
```json
{
  "user_id": "U1234567890abcdef",
  "message": "您好！這是管理員發送的訊息。"
}
```

**回應**:
```json
{
  "success": true,
  "message": "訊息發送成功"
}
```

#### POST /admin/api/broadcast
廣播訊息給所有使用者。

**認證**: 需要登入

**請求體**:
```json
{
  "message": "系統維護通知：將於今晚 22:00-24:00 進行系統維護。",
  "language": "zh-TW"
}
```

**回應**:
```json
{
  "success": true,
  "sent_count": 150
}
```

## 資料庫 API

### 7. 垃圾資訊 API

#### GET /api/waste-info/{category}
取得特定類別的垃圾資訊。

**參數**:
- `category` (string): 垃圾類別 (plastic, paper, metal, glass, organic, battery, electronics, other)
- `language` (string, 選填): 語言代碼，預設 zh-TW

**回應**:
```json
{
  "category": "plastic",
  "category_name": "塑膠類",
  "disposal_method": "清洗乾淨後壓扁，投入塑膠類回收桶",
  "tips": "記得撕掉標籤和瓶蓋"
}
```

#### GET /api/waste-search
搜尋垃圾資訊。

**查詢參數**:
- `q` (string): 搜尋關鍵字
- `language` (string, 選填): 語言代碼，預設 zh-TW

**回應**:
```json
{
  "results": [
    {
      "category": "plastic",
      "category_name": "塑膠類",
      "name": "塑膠瓶",
      "disposal_method": "清洗乾淨後壓扁，投入塑膠類回收桶",
      "tips": "記得撕掉標籤和瓶蓋"
    }
  ],
  "total": 1
}
```

### 8. 環保新聞 API

#### GET /api/news
取得環保新聞列表。

**查詢參數**:
- `language` (string, 選填): 語言代碼，預設 zh-TW
- `limit` (int, 選填): 數量限制，預設 10

**回應**:
```json
{
  "news": [
    {
      "title": "環保署推動塑膠減量政策",
      "summary": "環保署宣布新的塑膠減量政策...",
      "url": "https://www.epa.gov.tw/news/123",
      "published_at": "2024-01-01T00:00:00Z",
      "source": "環保署"
    }
  ],
  "total": 10
}
```

### 9. 回收站 API

#### GET /api/recycling-stations
取得回收站列表。

**查詢參數**:
- `latitude` (float, 選填): 緯度
- `longitude` (float, 選填): 經度
- `radius` (float, 選填): 搜尋半徑（公里），預設 5

**回應**:
```json
{
  "stations": [
    {
      "id": 1,
      "name": "台北市環保局回收站",
      "address": "台北市信義區市府路1號",
      "latitude": 25.0375,
      "longitude": 121.5637,
      "phone": "02-2720-8889",
      "hours": "週一至週五 8:00-17:00",
      "city": "台北市",
      "distance": 1.2
    }
  ],
  "total": 1
}
```

## 錯誤處理

### 錯誤回應格式

所有 API 錯誤都遵循以下格式：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "錯誤描述",
    "details": "詳細資訊（選填）"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 常見錯誤代碼

| 代碼 | HTTP 狀態碼 | 描述 |
|------|-------------|------|
| `INVALID_REQUEST` | 400 | 請求格式錯誤 |
| `UNAUTHORIZED` | 401 | 未授權 |
| `FORBIDDEN` | 403 | 禁止訪問 |
| `NOT_FOUND` | 404 | 資源不存在 |
| `RATE_LIMITED` | 429 | 請求過於頻繁 |
| `INTERNAL_ERROR` | 500 | 內部伺服器錯誤 |
| `SERVICE_UNAVAILABLE` | 503 | 服務不可用 |

### 錯誤範例

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "缺少必要參數",
    "details": "user_id 參數為必填"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 速率限制

- **一般 API**: 每分鐘 100 次請求
- **管理後台 API**: 每分鐘 60 次請求
- **Webhook**: 無限制（由 LINE 平台控制）

## 認證

### LINE Bot 認證

LINE Bot API 使用 Channel Access Token 進行認證：

```
Authorization: Bearer <CHANNEL_ACCESS_TOKEN>
```

### 管理後台認證

管理後台使用 Session 認證，需要先透過登入端點獲取 Session。

## 使用範例

### 1. 發送訊息給使用者

```bash
curl -X POST "https://your-domain.com/admin/api/send-message" \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<session_cookie>" \
  -d '{
    "user_id": "U1234567890abcdef",
    "message": "您好！這是管理員發送的訊息。"
  }'
```

### 2. 取得統計資料

```bash
curl -X GET "https://your-domain.com/admin/api/stats" \
  -H "Cookie: session=<session_cookie>"
```

### 3. 搜尋垃圾資訊

```bash
curl -X GET "https://your-domain.com/api/waste-search?q=塑膠瓶&language=zh-TW"
```

## 版本歷史

### v1.0.0 (2024-01-01)
- 初始版本發布
- 支援基本的垃圾分類功能
- 管理後台 API
- 多語言支援

## 支援

如有問題或建議，請聯絡：
- Email: support@example.com
- GitHub Issues: https://github.com/your-repo/issues

---

**最後更新**: 2024-01-01
