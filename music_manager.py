"""
Müzik Yöneticisi — Yerel Klasör
C:\\Users\\yusuf.bas\\youtube_agent\\shortmusic klasöründen müzik seçer.
Dosya adında kategori adı geçiyorsa onu kullanır, bulamazsa 1.mp3 veya ilk dosyayı alır.
"""

import os
import glob
import random
import numpy as np
from pathlib import Path

MUSIC_DIR = r"C:\Users\yusuf.bas\youtube_agent\shortmusic"

# Söz kategorisi → aranacak anahtar kelimeler (dosya adında)
CATEGORY_KEYWORDS = {
    "motivasyon":      ["motivasyon", "motivation", "epik", "epic", "guc", "power"],
    "kisisel gelisim": ["kisisel", "gelisim", "personal", "yasam", "life"],
    "kisisel_gelisim": ["kisisel", "gelisim", "personal", "yasam", "life"],
    "ozlu soz":        ["ozlu", "unlu", "felsefe", "wisdom", "deep"],
    "ozlu_soz":        ["ozlu", "unlu", "felsefe", "wisdom", "deep"],
    "unlu alinti":     ["unlu", "ozlu", "alinti", "quote", "wisdom"],
    "unlu_alinti":     ["unlu", "ozlu", "alinti", "quote", "wisdom"],
    "dini":            ["din", "dini", "spiritual", "huzur", "calm", "peace"],
    "ask iliskiler":   ["ask", "love", "romantic", "duygusal", "emotional"],
    "ask_iliskiler":   ["ask", "love", "romantic", "duygusal", "emotional"],
    "yasam felsefesi": ["yasam", "life", "kisisel", "gelisim", "felsefe"],
    "yasam_felsefesi": ["yasam", "life", "kisisel", "gelisim", "felsefe"],
}

# Görsel içerik → aranacak anahtar kelimeler
VISUAL_KEYWORDS = {
    "nature":   ["huzur", "calm", "peace", "doga", "nature", "din"],
    "ocean":    ["huzur", "calm", "peace", "ocean"],
    "forest":   ["huzur", "calm", "doga", "nature"],
    "mountain": ["epik", "epic", "motivasyon", "guc"],
    "city":     ["motivasyon", "epik", "kisisel"],
    "urban":    ["motivasyon", "epik", "kisisel"],
    "person":   ["duygusal", "ask", "emotional"],
    "people":   ["duygusal", "ask", "emotional"],
    "sunset":   ["duygusal", "ask", "huzur"],
    "abstract": ["epik", "motivasyon", "felsefe"],
    "space":    ["epik", "felsefe", "derin"],
    "fire":     ["motivasyon", "epik", "guc"],
    "water":    ["huzur", "calm", "dini"],
    "sky":      ["huzur", "ozlu", "felsefe"],
}


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


def analyze_video_content(video_path: str) -> str:
    """Claude ile videonun içeriğini analiz eder."""
    try:
        import base64, io
        from PIL import Image
        from moviepy.editor import VideoFileClip
        import anthropic, httpx
        from config import ANTHROPIC_API_KEY

        clip  = VideoFileClip(video_path)
        frame = clip.get_frame(min(1.0, clip.duration / 2))
        clip.close()

        img = Image.fromarray(frame).resize((512, 512), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        http   = httpx.Client(verify=False)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)

        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=20,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                    {"type": "text", "text": "Bu goruntudeki sahneyi tek kelimeyle tanımla. Sadece su seceneklerden birini yaz: nature, ocean, forest, mountain, city, urban, person, people, sunset, abstract, space, fire, water, sky"}
                ]
            }]
        )
        content = resp.content[0].text.strip().lower()
        print(f"  → Video icerigi: {content}")
        return content
    except Exception as e:
        print(f"  ⚠ Video analizi basarisiz: {e}")
        return "abstract"


def get_music(video_path: str, quote: dict) -> str:
    """
    Video içeriği + söz kategorisine göre müzik seçer.
    1. Kategori adıyla dosya ara
    2. Görsel içerikle dosya ara
    3. Fallback: 1.mp3 veya ilk dosya
    4. Son çare: yazılımla üret
    """
    files = get_all_music_files()

    if not files:
        print(f"  ⚠ {MUSIC_DIR} klasöründe müzik yok! Yazılımla üretiliyor...")
        return generate_software_music(60)

    category = (quote.get("category") or "").lower()
    print(f"  → Müzik aranıyor (kategori: {category})")

    # 1. Kategori anahtar kelimesiyle ara
    keywords = CATEGORY_KEYWORDS.get(category, [])
    if keywords:
        match = find_music_by_keywords(keywords)
        if match:
            print(f"  → Kategori müziği: {os.path.basename(match)}")
            return match

    # 2. Görsel içerikle ara (bağlantı varsa)
    try:
        visual = analyze_video_content(video_path)
        vis_kw = VISUAL_KEYWORDS.get(visual, [])
        if vis_kw:
            match = find_music_by_keywords(vis_kw)
            if match:
                print(f"  → Görsel müzik: {os.path.basename(match)}")
                return match
    except:
        pass

    # 3. Fallback: 1.mp3 veya ilk dosya
    fb = get_fallback_music()
    if fb:
        print(f"  → Fallback müzik: {os.path.basename(fb)}")
        return fb

    # 4. Son çare: yazılımla üret
    print("  ⚠ Hiç müzik bulunamadı, yazılımla üretiliyor...")
    return generate_software_music(60)


def generate_software_music(duration: float) -> str:
    """Yazılımla ambient müzik üretir (son çare)."""
    from moviepy.audio.AudioClip import AudioArrayClip

    Path("output/tmp").mkdir(parents=True, exist_ok=True)
    out = "output/tmp/sw_music.wav"

    sr = 44100
    t  = np.linspace(0, duration, int(sr * duration))
    wave = (
        0.35 * np.sin(2 * np.pi * 174.6 * t) +
        0.28 * np.sin(2 * np.pi * 261.6 * t) +
        0.22 * np.sin(2 * np.pi * 349.2 * t) +
        0.18 * np.sin(2 * np.pi * 523.2 * t)
    )
    wave *= (1 + 0.04 * np.sin(2 * np.pi * 0.3 * t))
    fade  = int(sr * 2.0)
    wave[:fade]  *= np.linspace(0, 1, fade)
    wave[-fade:] *= np.linspace(1, 0, fade)

    stereo = np.column_stack([wave, wave]).astype(np.float32)
    AudioArrayClip(stereo, fps=sr).write_audiofile(out, fps=sr, logger=None)
    return out


if __name__ == "__main__":
    print(f"Müzik klasörü: {MUSIC_DIR}")
    files = get_all_music_files()
    print(f"Bulunan dosyalar ({len(files)}):")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    if not files:
        print(f"\n⚠ Klasör boş veya yok: {MUSIC_DIR}")
        print("Lütfen müzik dosyalarını bu klasöre koyun.")
    else:
        print("\nKategori eşleşme testi:")
        for cat in ["motivasyon", "dini", "ozlu soz", "ask iliskiler"]:
            kw = CATEGORY_KEYWORDS.get(cat, [])
            match = find_music_by_keywords(kw)
            print(f"  {cat}: {os.path.basename(match) if match else 'YOK → fallback'}")
