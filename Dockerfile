# 使用 Python 3.9 官方映像
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製需求檔案
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式檔案
COPY . .

# 建立必要的目錄
RUN mkdir -p models temp data

# 初始化資料庫
RUN python database.py

# 暴露端口
EXPOSE 5000

# 設定環境變數
ENV FLASK_APP=main.py
ENV FLASK_ENV=production

# 啟動應用程式
CMD ["python", "main.py"]
