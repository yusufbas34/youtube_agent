"""
Söz Video Üreticisi
- Stok video üzerine sadece yazı (arka plan yok)
- Özel font: Painter_PERSONAL_USE_ONLY.ttf
- Yazı tam ortada
- Edge TTS seslendirme
- Freesound müzik
"""

import os, re, glob, json, random, asyncio
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
)
import edge_tts
from music_manager import get_music

STOCK_DIR  = r"C:\Users\yusuf.bas\youtube_agent\shortsvideo"
FONT_PATH  = r"C:\Users\yusuf.bas\youtube_agent\font\Painter_PERSONAL_USE_ONLY.ttf"
VOICE      = "tr-TR-EmelNeural"
VIDEO_SIZE = (1080, 1920)


def get_font(size):
    if os.path.exists(FONT_PATH):
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except:
            pass
    # fallback
    for p in ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


def wrap_text(text, font, max_w, draw):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textbbox((0,0), test, font=font)[2] > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def make_quote_overlay(quote: dict, size=VIDEO_SIZE) -> np.ndarray:
    """
    Şeffaf overlay — sadece yazı, tam ortada.
    Arka plan yok, sadece metin ve gölge.
    """
    w, h = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    text   = quote.get("text", "")
    author = quote.get("author", "")
    if author and author != "Anonim":
        author_line = "— " + author
    else:
        author_line = ""

    # Font boyutu metne göre ayarla
    fs = 72 if len(text) < 60 else 60 if len(text) < 100 else 50
    main_font = get_font(fs)
    lines = wrap_text(text, main_font, w - 120, draw)

    # Satır yüksekliği
    line_h    = int(fs * 1.45)
    total_h   = len(lines) * line_h
    # Yazar varsa ekstra boşluk
    auth_h    = int(fs * 0.7) if author_line else 0
    block_h   = total_h + (20 + auth_h if author_line else 0)

    # Tam orta
    start_y = (h - block_h) // 2

    # Her satırı çiz
    for i, line in enumerate(lines):
        y = start_y + i * line_h
        # Siyah kalın gölge (4 yönde)
        for ox, oy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,-4),(0,4),(-4,0),(4,0)]:
            draw.text((w//2+ox, y+oy), line, font=main_font,
                      fill=(0,0,0,220), anchor="mm")
        # Beyaz ana yazı
        draw.text((w//2, y), line, font=main_font,
                  fill=(255,255,255,255), anchor="mm")

    # Yazar satırı
    if author_line:
        auth_font = get_font(int(fs * 0.55))
        ay = start_y + total_h + 20
        for ox, oy in [(-2,-2),(2,-2),(-2,2),(2,2)]:
            draw.text((w//2+ox, ay+oy), author_line, font=auth_font,
                      fill=(0,0,0,180), anchor="mm")
        draw.text((w//2, ay), author_line, font=auth_font,
                  fill=(220,220,220,230), anchor="mm")

    return np.array(overlay)


async def _tts(text, path):
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    comm = edge_tts.Communicate(text=text, voice=VOICE, rate="+0%")
    await comm.save(path)


def generate_tts(text, path):
    asyncio.run(_tts(text, path))
    return path


def pick_stock_video(exclude=None):
    videos = []
    for ext in ["*.mp4","*.MP4","*.mov","*.MOV"]:
        videos += glob.glob(os.path.join(STOCK_DIR, ext))
    if not videos:
        raise FileNotFoundError("Stok video bulunamadi: " + STOCK_DIR)
    avail = [v for v in videos if not (exclude and v in exclude)] or videos
    return random.choice(avail)


def create_quote_video(quote: dict, output_path: str,
                       stock_video_path: str = None) -> str:
    print("  → Video uretiliyor: " + quote.get("text","")[:50] + "...")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path("output/tmp")
    tmp.mkdir(parents=True, exist_ok=True)

    if not stock_video_path:
        stock_video_path = pick_stock_video()
    print("  → Stok video: " + os.path.basename(stock_video_path))

    # TTS
    tts_path = str(tmp / "q_tts.mp3")
    tts_text = quote.get("text","")
    if quote.get("author") and quote["author"] != "Anonim":
        tts_text += ". " + quote["author"] + "."
    generate_tts(tts_text, tts_path)
    tts_audio    = AudioFileClip(tts_path)
    tts_duration = tts_audio.duration + 1.8

    # Muzik
    print("  → Muzik seciliyor...")
    music_path = get_music(stock_video_path, quote)

    # Stok video yukle ve 9:16 yap
    stock = VideoFileClip(stock_video_path)
    sw, sh = stock.size
    ratio  = VIDEO_SIZE[0] / VIDEO_SIZE[1]
    if sw/sh > ratio:
        new_w = int(sh * ratio)
        stock = stock.crop(x_center=sw/2, width=new_w)
    else:
        new_h = int(sw / ratio)
        stock = stock.crop(y_center=sh/2, height=new_h)
    stock = stock.resize(VIDEO_SIZE).without_audio()

    # Dongu gerekiyorsa
    if tts_duration > stock.duration:
        loops = int(np.ceil(tts_duration / stock.duration))
        print("  → Video " + str(loops) + "x donguye alindi")
        stock = concatenate_videoclips([stock] * loops)
    stock = stock.subclip(0, tts_duration)

    # Overlay ekle
    overlay_arr = make_quote_overlay(quote, VIDEO_SIZE)
    overlay_img = Image.fromarray(overlay_arr)

    def add_overlay(frame):
        base = Image.fromarray(frame).convert("RGBA")
        base.paste(overlay_img, (0,0), overlay_img)
        return np.array(base.convert("RGB"))

    final_video = stock.fl_image(add_overlay)

    # Muzik
    music_audio = AudioFileClip(music_path)
    if music_audio.duration < tts_duration:
        from moviepy.editor import concatenate_audioclips
        loops = int(np.ceil(tts_duration / music_audio.duration))
        music_audio = concatenate_audioclips([music_audio] * loops)
    music_audio = music_audio.subclip(0, tts_duration).volumex(0.55)
    tts_audio   = tts_audio.set_start(0.5)
    final_audio = CompositeAudioClip([tts_audio, music_audio])
    final_video = final_video.set_audio(final_audio)

    # Export
    print("  → Disa aktariliyor...")
    final_video.write_videofile(
        output_path, fps=24,
        codec="libx264", audio_codec="aac",
        logger=None, threads=4
    )

    for f in tmp.glob("q_*"):
        try: f.unlink()
        except: pass

    mb = os.path.getsize(output_path) / (1024*1024)
    print("  Video hazir: " + output_path + " (" + str(round(mb,1)) + " MB)")
    return output_path


if __name__ == "__main__":
    from quotes_manager import get_next_quote, refresh_quotes
    refresh_quotes()
    quote = get_next_quote()
    print("Soz: " + quote["text"])
    create_quote_video(quote, "output/test_quote.mp4")


def clear_music_cache():
    """Eski müzik önbelleğini temizler — ses sorunu varsa çalıştır."""
    import glob, os
    for f in glob.glob("music_cache/*.wav") + glob.glob("music_cache/*.mp3"):
        try:
            os.remove(f)
            print(f"Silindi: {f}")
        except: pass
    if os.path.exists("music_cache/index.json"):
        os.remove("music_cache/index.json")
    print("Muzik onbellegi temizlendi. Bir sonraki videoda yeniden uretilecek.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--clear-music":
        clear_music_cache()
    else:
        from quotes_manager import get_next_quote, refresh_quotes
        refresh_quotes()
        quote = get_next_quote()
        print("Soz: " + quote["text"])
        create_quote_video(quote, "output/test_quote.mp4")
