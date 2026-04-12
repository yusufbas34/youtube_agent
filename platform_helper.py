"""
Platform yardımcısı — Windows ve Linux arasında otomatik geçiş yapar.
"""
import os
import platform

IS_WINDOWS = platform.system() == "Windows"
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))

# ── yt-dlp yolu ───────────────────────────────────────────────────
if IS_WINDOWS:
    YTDLP_PATH = os.path.join(BASE_DIR, "yt-dlp.exe")
else:
    YTDLP_PATH = "/usr/local/bin/yt-dlp"

# ── Font yolları ──────────────────────────────────────────────────
FONT_DIR = os.path.join(BASE_DIR, "font")

FONT_PATHS = [
    os.path.join(FONT_DIR, "Montserrat-Bold.ttf"),
    os.path.join(FONT_DIR, "Montserrat-ExtraBold.ttf"),
]

if IS_WINDOWS:
    FONT_PATHS += [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        r"C:\Windows\Fonts\verdanab.ttf",
    ]
else:
    FONT_PATHS += [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

# ── Logo yolu ─────────────────────────────────────────────────────
LOGO_PATH = os.path.join(BASE_DIR, "tarihtennotlargiriscikis.png")

# ── Output dizinleri ──────────────────────────────────────────────
def ensure_dirs():
    for d in ["output/sozler", "output/tarih", "output/viral",
              "output/tmp", "data", "music_cache"]:
        os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)
