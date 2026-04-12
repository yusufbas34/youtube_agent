FROM python:3.11-slim

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-liberation \
    fonts-dejavu-core \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp Linux binary indir
RUN wget -O /usr/local/bin/yt-dlp https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    && chmod +x /usr/local/bin/yt-dlp

# Montserrat font indir
RUN mkdir -p /app/font \
    && wget -O /app/font/Montserrat-Bold.ttf \
       "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf" \
    && wget -O /app/font/Montserrat-ExtraBold.ttf \
       "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-ExtraBold.ttf"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Klasörleri oluştur
RUN mkdir -p output/sozler output/tarih output/viral data music_cache

EXPOSE 5051

CMD ["python", "dashboard_server.py"]
