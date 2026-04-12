"""
YouTube AI Agent - Konfigürasyon
Railway'de environment variable'lardan okur, lokalde .env dosyasından.
"""
import os

# .env dosyası varsa yükle (lokal geliştirme için)
try:
    from dotenv import load_dotenv
    load_dotenv()
except: pass

# ─── API Anahtarları ───────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.environ.get("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", "")
YOUTUBE_API_KEY     = os.environ.get("AIzaSyDme2fxs3BtXZIoR294_jhsqT4aWLxUH_I", "")
ELEVENLABS_API_KEY  = os.environ.get("sk_6f96d9eb0e3a96f03ba5866049174c30e4e011e1318fc3d5", "")
TELEGRAM_BOT_TOKEN  = os.environ.get("8267199854:AAGtwVuUB7Yn2YZhNqWG3RJ5zNDGWKk4WSU", "")
TELEGRAM_CHAT_ID    = os.environ.get("1137512236", "")
PIXABAY_API_KEY     = os.environ.get("PIXABAY_API_KEY", "55256954-4e774f9bedfa0d1f2fe7efe0a")
PEXELS_API_KEY      = os.environ.get("PEXELS_API_KEY", "")

# ─── Video Servisleri ─────────────────────────────────────────────
VIDEO_PROVIDER = "runway"
RUNWAY_API_KEY = os.environ.get("RUNWAY_API_KEY", "")
HEYGEN_API_KEY = os.environ.get("HEYGEN_API_KEY", "")

# ─── Kanal Ayarları ───────────────────────────────────────────────
CHANNEL_NICHE     = "motivasyon"
CHANNEL_LANGUAGE  = "tr"
TARGET_AUDIENCE   = "18-35 yaş"

# ─── Yükleme Ayarları ─────────────────────────────────────────────
UPLOAD_TIME      = os.environ.get("UPLOAD_TIME", "18:00")
UPLOAD_TIMEZONE  = "Europe/Istanbul"
VIDEO_PRIVACY    = "public"
VIDEO_CATEGORY_ID = "28"

# ─── İçerik Ayarları ──────────────────────────────────────────────
VIDEO_DURATION_SECONDS = 60
VIDEO_STYLE = "shorts"
MAX_TAGS    = 15

# ─── OAuth2 Dosya Yolu ────────────────────────────────────────────
OAUTH_CREDENTIALS_FILE = "credentials.json"
OAUTH_TOKEN_FILE       = "token.json"

# ─── Platform Algılama ────────────────────────────────────────────
import platform
IS_WINDOWS = platform.system() == "Windows"
IS_RAILWAY = os.environ.get("RAILWAY_ENVIRONMENT") is not None
