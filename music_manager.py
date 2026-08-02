"""
Müzik Yöneticisi — Yerel Klasör
C:\\Users\\yusuf.bas\\youtube_agent\\shortmusic klasöründen müzik seçer.
Dosya adında kategori adı geçiyorsa onu kullanır, bulamazsa 1.mp3 veya ilk dosyayı alır.
"""

import os
import glob
import random

TARIH_MUSIC_URL   = "https://raw.githubusercontent.com/yusufbas34/youtube_agent/main/shortmusic/tariharkafonmusik.mp3"
TARIH_MUSIC_CACHE = "/tmp/tariharkafonmusik.mp3"


def get_tarih_music() -> str:
    import requests
    if os.path.exists(TARIH_MUSIC_CACHE) and os.path.getsize(TARIH_MUSIC_CACHE) > 10000:
        return TARIH_MUSIC_CACHE
    try:
        print("  🎵 Tarih muzigi indiriliyor...")
        r = requests.get(TARIH_MUSIC_URL, timeout=30)
        if r.status_code == 200:
            with open(TARIH_MUSIC_CACHE, "wb") as f:
                f.write(r.content)
            print(f"  ✅ Tarih muzigi hazir ({len(r.content)//1024}KB)")
            return TARIH_MUSIC_CACHE
        else:
            print(f"  ⚠ Tarih muzigi indirilemedi: {r.status_code}")
    except Exception as e:
        print(f"  ⚠ Tarih muzigi hata: {e}")
    return None


MUSIC_DIR = r"C:\Users\yusuf.bas\youtube_agent\shortmusic"


def get_all_music_files() -> list:
    """Müzik klasöründeki tüm ses dosyalarını listeler."""
    files = []
    for ext in ["*.mp3", "*.MP3", "*.wav", "*.WAV", "*.m4a", "*.M4A", "*.ogg"]:
        files += glob.glob(os.path.join(MUSIC_DIR, ext))
    return sorted(files)


def find_music_by_keywords(keywords: list) -> str | None:
    """Dosya adında anahtar kelime geçen müziği bulur."""
    files = get_all_music_files()
    if not files:
        return None

    # Tam eşleşme ara
    for kw in keywords:
        matches = [f for f in files if kw.lower() in os.path.basename(f).lower()]
        if matches:
            return random.choice(matches)
    return None


def get_fallback_music() -> str | None:
    """'1' içeren dosyayı veya ilk dosyayı döner."""
    files = get_all_music_files()
    if not files:
        return None

    # "1" geçen dosyayı bul
    ones = [f for f in files if "1" in os.path.splitext(os.path.basename(f))[0]]
    if ones:
        return ones[0]

    return files[0]


if __name__ == "__main__":
    print(f"Müzik klasörü: {MUSIC_DIR}")
    files = get_all_music_files()
    print(f"Bulunan dosyalar ({len(files)}):")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    if not files:
        print(f"\n⚠ Klasör boş veya yok: {MUSIC_DIR}")
        print("Lütfen müzik dosyalarını bu klasöre koyun.")
