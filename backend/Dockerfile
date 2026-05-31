FROM python:3.11-slim

# システム依存パッケージのインストール
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pythonパッケージのインストール（キャッシュ活用のため先にコピー）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# メディアディレクトリを作成
RUN mkdir -p /app/media/audio /app/media/video /app/media/temp

# デフォルトはAPIサーバー起動（docker-compose.ymlでワーカーは上書き）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
