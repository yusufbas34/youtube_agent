"""
Müzik Yöneticisi — Cross Platform
Windows'ta yerel klasörden, Railway'de /app/shortmusic'ten okur.
"""

import os, glob, random, platform
import numpy as np
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"
MUSIC_DIR  = r"C:\Users\yusuf.bas\youtube_agent\shortmusic" if IS_WINDOWS else "/app/shortmusic"

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
    files = []
    for ext in ["*.mp3", "*.MP3", "*.wav", "*.WAV", "*.m4a", "*.M4A", "*.ogg"]:
        files += glob.glob(os.path.join(MUSIC_DIR, ext))
    return sorted(files)


def find_music_by_keywords(keywords: list):
    files = get_all_music_files()
    if not files:
        return None
    for kw in keywords:
        matches = [f for f in files if kw.lower() in os.path.basename(f).lower()]
        if matches:
            return random.choice(matches)
    return None


def get_fallback_music():
    files = get_all_music_files()
    if not files:
        return None
    ones = [f for f in files if "1" in os.path.splitext(os.path.basename(f))[0]]
    return ones[0] if ones else files[0]


def analyze_video_content(video_path: str) -> str:
    """Video içeriğini analiz eder — müzik klasörü yoksa atla."""
    if not os.path.exists(MUSIC_DIR):
        return "abstract"
    try:
        import base64, io
        from PIL import Image
        from moviepy.editor import VideoFileClip
        import anthropic, httpx
        from config import ANTHROPIC_API_KEY

        clip  = VideoFileClip(video_path)
        frame = clip.get_frame(min(1.0, clip.duration / 2))
        clip.close()

        img    = Image.fromarray(frame).resize((512, 512), Image.LANCZOS)
        buf    = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        http   = httpx.Client(verify=False)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)
        resp   = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=20,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text": "Bu goruntudeki sahneyi tek kelimeyle tanımla. Sadece su seceneklerden birini yaz: nature, ocean, forest, mountain, city, urban, person, people, sunset, abstract, space, fire, water, sky"}
            ]}]
        )
        content = resp.content[0].text.strip().lower()
        print(f"  → Video icerigi: {content}")
        return content
    except Exception as e:
        print(f"  ⚠ Video analizi basarisiz: {e}")
        return "abstract"


def get_music(video_path: str, quote: dict) -> str:
    files = get_all_music_files()

    if not files:
        print(f"  ⚠ Müzik bulunamadı, yazılımla üretiliyor...")
        return generate_software_music(60)

    category = (quote.get("category") or "").lower()
    print(f"  → Müzik aranıyor (kategori: {category})")

    # 1. Kategori ile ara
    keywords = CATEGORY_KEYWORDS.get(category, [])
    if keywords:
        match = find_music_by_keywords(keywords)
        if match:
            print(f"  → Kategori müziği: {os.path.basename(match)}")
            return match

    # 2. Görsel analiz (sadece yerel müzik varsa)
    try:
        if os.path.exists(MUSIC_DIR):
            visual = analyze_video_content(video_path)
            vis_kw = VISUAL_KEYWORDS.get(visual, [])
            if vis_kw:
                match = find_music_by_keywords(vis_kw)
                if match:
                    print(f"  → Görsel müzik: {os.path.basename(match)}")
                    return match
    except:
        pass

    # 3. Fallback
    fb = get_fallback_music()
    if fb:
        print(f"  → Fallback müzik: {os.path.basename(fb)}")
        return fb

    # 4. Yazılımla üret
    print("  ⚠ Hiç müzik bulunamadı, yazılımla üretiliyor...")
    return generate_software_music(60)


def generate_software_music(duration: float) -> str:
    from moviepy.audio.AudioClip import AudioArrayClip
    Path("output/tmp").mkdir(parents=True, exist_ok=True)
    out = "output/tmp/sw_music.wav"
    sr  = 44100
    t   = np.linspace(0, duration, int(sr * duration))
    wave = (
        0.35 * np.sin(2 * np.pi * 174.6 * t) +
        0.28 * np.sin(2 * np.pi * 261.6 * t) +
        0.22 * np.sin(2 * np.pi * 349.2 * t) +
        0.18 * np.sin(2 * np.pi * 523.2 * t)
    )
    wave *= (1 + 0.04 * np.sin(2 * np.pi * 0.3 * t))
    fade = int(sr * 2.0)
    wave[:fade]  *= np.linspace(0, 1, fade)
    wave[-fade:] *= np.linspace(1, 0, fade)
    stereo = np.column_stack([wave, wave]).astype(np.float32)
    AudioArrayClip(stereo, fps=sr).write_audiofile(out, fps=sr, logger=None)
    return out
