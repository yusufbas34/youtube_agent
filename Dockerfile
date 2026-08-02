FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-liberation \
    fonts-dejavu-core \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN wget -O /usr/local/bin/yt-dlp https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    && chmod +x /usr/local/bin/yt-dlp

RUN mkdir -p /app/font \
    && wget -O /app/font/Montserrat-Bold.ttf \
       "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf" \
    && wget -O /app/font/Montserrat-ExtraBold.ttf \
       "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-ExtraBold.ttf"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN mkdir -p output/tarih output/notesofhistory data music_cache

EXPOSE 5051
CMD ["python", "dashboard_server.py"]
