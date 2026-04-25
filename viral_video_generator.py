"""
Viral Kanal Video Üreticisi v2
- yt-dlp ile tweet videosunu indirir
- 9:16 crop + metin overlay
- TTS seslendirme
"""

import os, json, re, subprocess, asyncio, ssl
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip,
    concatenate_audioclips
)
import edge_tts

W, H       = 1080, 1920
FPS        = 30
OUTPUT_DIR = Path("output/viral")
TMP_DIR    = Path("output/tmp")
from platform_helper import YTDLP_PATH
from platform_helper import FONT_PATHS


def get_font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()


async def _tts(text, path):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    comm = edge_tts.Communicate(
        text=text[:500], voice="tr-TR-EmelNeural", rate="+10%"
    )
    await comm.save(path)


def generate_tts(text, path):
    asyncio.run(_tts(text, path))


def download_with_ytdlp(tweet_url: str, output_path: str) -> bool:
    """yt-dlp ile tweet videosunu indirir."""
    try:
        cmd = [
            YTDLP_PATH,
            "--no-check-certificate",
            "-f", "mp4/best[ext=mp4]/best",
            "--no-playlist",
            "-o", output_path,
            "--quiet",
            "--no-warnings",
            tweet_url
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if r.returncode == 0 and os.path.exists(output_path):
            if os.path.getsize(output_path) > 10000:
                print(f"  ✅ Video indirildi ({os.path.getsize(output_path)//1024}KB)")
                return True
        if r.stderr: print(f"  ⚠ yt-dlp: {r.stderr[:150]}")
    except Exception as e:
        print(f"  ⚠ yt-dlp hata: {e}")
    return False


def make_overlay_frame(text: str, w: int, h: int) -> Image.Image:
    """
    Breaking news stili metin overlay.
    Alt kısımda büyük, okunaklı, kırmızı bantlı.
    """
    overlay = Image.new("RGBA", (w, h), (0,0,0,0))
    draw    = ImageDraw.Draw(overlay)

    # Metin wrap
    font  = get_font(54)
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = (cur+" "+word).strip()
        if draw.textbbox((0,0),test,font=font)[2] > w-80 and cur:
            lines.append(cur); cur=word
        else: cur=test
    if cur: lines.append(cur)
    lines = lines[:4]

    lh      = 72
    total_h = len(lines)*lh + 140  # metin + üst etiket + boşluk
    grad_h  = total_h + 60

    # Alt koyu gradient
    for y in range(grad_h):
        a = int(240*(1-y/grad_h)**0.5)
        draw.line([(0,h-grad_h+y),(w,h-grad_h+y)], fill=(0,0,0,a))

    # Kırmızı üst çizgi
    bar_y = h - grad_h
    draw.rectangle([(0,bar_y),(w,bar_y+5)], fill=(220,38,38,255))

    # ⚡ VİRAL etiketi
    lf    = get_font(26)
    label = "⚡ VİRAL"
    lb    = draw.textbbox((0,0),label,font=lf)
    lw    = lb[2]
    draw.rounded_rectangle([30,bar_y+12,lw+54,bar_y+50],
                           radius=4, fill=(220,38,38,240))
    draw.text((42,bar_y+16), label, font=lf, fill=(255,255,255,255))

    # Metin satırları
    ty = h - len(lines)*lh - 55
    for line in lines:
        bb = draw.textbbox((0,0),line,font=font)
        lw = bb[2]
        x  = (w-lw)//2
        # Gölge
        for ox,oy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,-4),(0,4),(-4,0),(4,0)]:
            draw.text((x+ox,ty+oy),line,font=font,fill=(0,0,0,220))
        # Ana metin
        draw.text((x,ty),line,font=font,fill=(255,255,255,255))
        ty += lh

    return overlay


def create_viral_video(tweet: dict, output_path: str = None) -> str | None:
    """Tweet URL'sinden yt-dlp ile video indirip overlay ekler."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"output/viral/viral_{ts}.mp4"

    raw_text   = tweet.get("text","")
    tweet_url  = tweet.get("link","")
    tweet_id   = tweet.get("tweet_id","x")

    # "Video" kelimesini her yerden temizle (baş, son, ortada)
    text = re.sub(r'\s*\bVideo\.?\s*$', '', raw_text, flags=re.IGNORECASE).strip()
    text = re.sub(r'^\s*\bVideo\.?\s*', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'\s*\bVid\.?\s*$', '', text, flags=re.IGNORECASE).strip()
    if not text:
        text = raw_text

    print(f"\n  📱 Viral video: {text[:50]}...")
    print(f"  🔗 URL: {tweet_url}")

    # 1. Video indir
    tmp_vid = str(TMP_DIR / f"tweet_{tweet_id}.mp4")
    if os.path.exists(tmp_vid):
        os.remove(tmp_vid)

    ok = False
    if tweet_url:
        print(f"  ⬇ yt-dlp ile indiriliyor...")
        ok = download_with_ytdlp(tweet_url, tmp_vid)

    # Tweet URL yoksa veya indirilemediyse YouTube'dan ara
    if not ok:
        search_query = tweet.get("search_query","")
        # search_query yoksa text'ten otomatik oluştur
        if not search_query and text:
            import re as _re
            # Türkçe metni İngilizce arama terimine çevir (basit)
            clean = _re.sub(r'[^\w\s]', ' ', text[:60]).strip()
            search_query = clean + " viral video short"
        if search_query:
            print(f"  🔍 YouTube'dan aranıyor: {search_query[:50]}")
            yt_url = f"ytsearch1:{search_query}"
            ok = download_with_ytdlp(yt_url, tmp_vid)

    if not ok:
        print(f"  ❌ Video indirilemedi, atlanıyor")
        return None

    # 2. Video yükle
    try:
        clip = VideoFileClip(tmp_vid)
    except Exception as e:
        print(f"  ❌ Video açılamadı: {e}")
        return None

    cw, ch   = clip.size
    duration = min(clip.duration, 59.0)
    clip     = clip.subclip(0, duration)

    # 3. 9:16 crop (siyah kenar olmadan)
    tgt = W / H
    if cw/ch > tgt:
        new_w = int(ch * tgt)
        clip  = clip.crop(x_center=cw/2, width=new_w)
    else:
        new_h = int(cw / tgt)
        clip  = clip.crop(y_center=ch/2, height=new_h)
    clip = clip.resize((W, H))

    # 4. Overlay ekle (PIL ile üretilmiş static frame)
    overlay_img = make_overlay_frame(text, W, H)
    overlay_arr = np.array(overlay_img)

    def apply_overlay(frame):
        base = Image.fromarray(frame).convert("RGBA")
        base.paste(Image.fromarray(overlay_arr), (0,0),
                  Image.fromarray(overlay_arr[:,:,3], 'L'))
        return np.array(base.convert("RGB"))

    clip = clip.fl_image(apply_overlay)

    # 5. Ses — sadece orijinal ses, TTS yok
    if clip.audio:
        audio = clip.audio.volumex(1.0)
        clip = clip.set_audio(audio)

    # 6. Export
    print(f"  💾 Kaydediliyor...")
    clip.write_videofile(
        output_path, fps=FPS,
        codec="libx264", audio_codec="aac",
        logger=None, threads=2,
        preset="ultrafast",
        ffmpeg_params=["-crf","26"]
    )

    # Bellek temizle
    try:
        clip.close()
    except: pass
    import gc; gc.collect()

    # Temizle
    for f in [tmp_vid]:
        try: os.remove(f)
        except: pass

    # Metadata
    meta = {
        "title":       (text[:85] + " #viral #shorts").strip(),
        "description": text + f"\n\nKaynak: {tweet_url}\n\n#viral #shorts #gundem #trending",
        "tags":        ["viral","shorts","gundem","trending","son dakika"],
        "hashtags":    ["#viral","#shorts","#gundem"],
        "tweet_id":    tweet_id,
        "source":      tweet.get("source",""),
        "channel":     "viral",
        "generated_at": datetime.now().isoformat(),
    }
    with open(output_path.replace(".mp4",".json"),"w",encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    mb = os.path.getsize(output_path)/(1024*1024)
    print(f"  ✅ Hazır: {output_path} ({mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    # Test - son tweet'i dene
    from viral_scraper import load_queue
    queue = load_queue()
    if queue:
        item = queue[0]
        print(f"Test tweet: {item['text'][:60]}")
        result = create_viral_video(item)
        print(f"Sonuç: {result}")
    else:
        print("Kuyruk boş, önce viral_scraper.py çalıştır")
