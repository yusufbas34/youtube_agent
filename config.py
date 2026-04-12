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
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
YOUTUBE_API_KEY     = os.environ.get("YOUTUBE_API_KEY", "")
ELEVENLABS_API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")
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
