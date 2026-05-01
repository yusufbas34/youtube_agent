"""
Tarih Kanalı Video Üreticisi v4
- Pixabay'den konuya özel gerçek görseller
- Montserrat font, yazı ortada
- Ken Burns zoom + dramatic overlay
- Siyah kenar yok
"""

import os, json, asyncio, ssl, requests, random, io, re
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from moviepy.editor import (
    VideoClip, AudioFileClip, CompositeAudioClip,
    concatenate_audioclips, concatenate_videoclips
)
import edge_tts

W, H       = 1080, 1920
FPS        = 20
OUTPUT_DIR = Path("output/tarih")

# Notes of History sabitleri
NOTES_OUTPUT_DIR     = Path("output/notesofhistory")
NOTES_VOICE_ID       = "1GCQiLWWVadqyDYY3CK9"
NOTES_OUTRO_PATH_WIN = "notesofhistory.png"
NOTES_OUTRO_PATH_LIN = "/app/notesofhistory.png"

from platform_helper import FONT_PATHS, LOGO_PATH, ensure_dirs
ensure_dirs()

try:
    from config import PIXABAY_API_KEY
except:
    PIXABAY_API_KEY = "55256954-4e774f9bedfa0d1f2fe7efe0a"

try:
    from config import PEXELS_API_KEY
except:
    PEXELS_API_KEY = ""


def get_font(size):
    for path in FONT_PATHS:
        if os.path.exists(path):
            try: return ImageFont.truetype(path, size)
            except: pass
    return ImageFont.load_default()


def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ── Görsel Çekici ─────────────────────────────────────────────────

def pick_ai_video_clip(visual_desc: str, topic: str, period: str,
                       seg_idx: int = 0, total: int = 6,
                       duration: float = 7.0) -> "np.ndarray | None":
    """Seedance 2.0 ile AI video klibi uret. Basarisiz olursa None doner."""
    try:
        from ai_video_generator import is_seedance_available, generate_segment_video, build_history_prompt
        if not is_seedance_available():
            return None
        prompt = build_history_prompt(visual_desc, topic, period, seg_idx, total)
        out = str(TMP_DIR / f"ai_{seg_idx}_{int(time.time())}.mp4")
        clip_path = generate_segment_video(
            prompt=prompt, duration=5,
            aspect_ratio="9:16", output_path=out
        )
        if not clip_path or not os.path.exists(clip_path):
            return None
        # VideoFileClip olarak yukle ve frame'e cevir
        from moviepy.editor import VideoFileClip as _VFC
        vc = _VFC(clip_path)
        # Ortadan 7 saniyelik frame sec
        t = min(0.5, vc.duration / 2)
        frame = vc.get_frame(t)
        vc.close()
        # 9:16 formatina getir
        img = Image.fromarray(frame.astype("uint8")).resize((W, H), Image.LANCZOS)
        return np.array(img)
    except Exception as e:
        print(f"  ⚠ AI video clip hatasi: {e}")
        return None


def fetch_images(queries: list, count: int = 6) -> list:
    """Pixabay'den görsel çeker, olmazsa Pexels dener."""
    results = []
    seen    = set()

    # Pixabay
    if PIXABAY_API_KEY:
        for q in queries:
            try:
                r = requests.get(
                    "https://pixabay.com/api/",
                    params={
                        "key":         PIXABAY_API_KEY,
                        "q":           q,
                        "per_page":    3,
                        "image_type":  "photo",
                        "orientation": "vertical",
                        "min_width":   800,
                        "min_height":  1000,
                        "safesearch":  "true",
                        "order":       "popular",
                    },
                    timeout=10, verify=False
                )
                if r.status_code == 200:
                    for hit in r.json().get("hits", []):
                        url = hit.get("largeImageURL","")
                        pid = hit.get("id","")
                        if url and pid not in seen:
                            seen.add(pid)
                            results.append(url)
                            print(f"  ✅ Pixabay: {q[:35]} → bulundu")
                elif r.status_code == 429:
                    print(f"  ⚠ Pixabay limit doldu")
                    break
            except Exception as e:
                print(f"  ⚠ Pixabay ({q[:25]}): {e}")
            if len(results) >= count:
                break

    # Pexels fallback
    if len(results) < count and PEXELS_API_KEY:
        for q in queries:
            try:
                r = requests.get(
                    "https://api.pexels.com/v1/search",
                    headers={"Authorization": PEXELS_API_KEY},
                    params={"query": q, "per_page": 3, "orientation": "portrait"},
                    timeout=10, verify=False
                )
                if r.status_code == 200:
                    for p in r.json().get("photos", []):
                        url = p.get("src",{}).get("large2x","")
                        pid = p.get("id","")
                        if url and pid not in seen:
                            seen.add(pid)
                            results.append(url)
            except: pass
            if len(results) >= count:
                break

    print(f"  → Toplam {len(results)} görsel URL bulundu")
    return results[:count]


def download_image(url: str) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=15, verify=False,
                        headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            if img.width >= 200 and img.height >= 200:
                return img
    except: pass
    return None


def prepare_for_shorts(img: Image.Image) -> Image.Image:
    """Siyah kenar olmadan 9:16'ya uyarla."""
    iw, ih  = img.size
    tgt     = W / H

    if iw / ih > tgt:
        # Çok geniş → yüksekliğe göre scale, yan kırp
        nh = H
        nw = int(iw * H / ih)
        img = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - W) // 2
        img  = img.crop((left, 0, left + W, H))
    else:
        # Çok uzun → genişliğe göre scale, ortadan kırp
        nw = W
        nh = int(ih * W / iw)
        img = img.resize((nw, nh), Image.LANCZOS)
        top = (nh - H) // 2
        img = img.crop((0, top, W, top + H))

    # Garanti: tam boyut
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)

    return img


def make_dramatic(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Contrast(img).enhance(1.3)
    img = ImageEnhance.Color(img).enhance(0.8)
    img = ImageEnhance.Brightness(img).enhance(0.88)
    return img


def make_fallback_image(accent_hex: str, idx: int) -> Image.Image:
    """Son çare: sinematik gradyan."""
    palettes = [
        [(20,5,2), (60,20,8)],
        [(2,8,25), (8,30,60)],
        [(5,2,20), (20,8,50)],
        [(25,12,2),(60,35,8)],
        [(2,15,10),(8,45,30)],
    ]
    c1, c2 = palettes[idx % len(palettes)]
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(c1[0]*(1-t) + c2[0]*t)
        g = int(c1[1]*(1-t) + c2[1]*t)
        b = int(c1[2]*(1-t) + c2[2]*t)
        draw.line([(0,y),(W,y)], fill=(r,g,b))
    # Işık odağı
    ac = hex_to_rgb(accent_hex)
    cx, cy = W//2, H//3
    for radius in range(500, 0, -30):
        ratio = 1 - radius/500
        ra = int(ac[0]*ratio*0.4 + c2[0]*ratio*0.3)
        ga = int(ac[1]*ratio*0.4 + c2[1]*ratio*0.3)
        ba = int(ac[2]*ratio*0.4 + c2[2]*ratio*0.3)
        draw.ellipse([cx-radius,cy-radius,cx+radius,cy+radius],
                    fill=(ra,ga,ba))
    return img


# ── Ken Burns ─────────────────────────────────────────────────────

def ease_out(t):
    return 1 - (1 - min(1.0, max(0.0, t)))**3


def ken_burns(img: Image.Image, t: float, duration: float,
              zoom_in=True, direction="center") -> np.ndarray:
    p    = min(1.0, t / max(duration, 0.01))
    zoom = 1.0 + 0.18*p if zoom_in else 1.18 - 0.18*p
    dirs = {
        "center": (0.5,  0.45),
        "left":   (0.35+0.15*p, 0.45),
        "right":  (0.65-0.15*p, 0.45),
        "up":     (0.5,  0.35+0.15*p),
        "down":   (0.5,  0.55-0.10*p),
    }
    cx, cy = dirs.get(direction, (0.5, 0.45))
    nw, nh = int(W*zoom), int(H*zoom)
    zoomed = img.resize((nw, nh), Image.LANCZOS)
    left   = max(0, min(int(cx*nw - W/2), nw-W))
    top    = max(0, min(int(cy*nh - H/2), nh-H))
    return np.array(zoomed.crop((left, top, left+W, top+H)))


# ── Text Overlay ──────────────────────────────────────────────────

def wrap_text(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur+" "+w).strip()
        if draw.textbbox((0,0),test,font=font)[2] > max_w and cur:
            lines.append(cur); cur=w
        else: cur=test
    if cur: lines.append(cur)
    return lines


def add_overlay(frame_arr, t, seg_text, seg_dur, accent_hex,
                title="", period="", seg_idx=0, total=1) -> np.ndarray:
    img     = Image.fromarray(frame_arr).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    draw    = ImageDraw.Draw(overlay)
    ac      = hex_to_rgb(accent_hex)

    fi = ease_out(t / 0.5)
    fo = ease_out((seg_dur-t)/0.4) if t > seg_dur-0.4 else 1.0
    alpha = min(fi, fo)

    # Alt gradient — sadece metin altında ince, siyah kutu yok
    for y in range(380):
        a = int(180 * ease_out(1-y/380) * alpha)
        draw.line([(0,H-380+y),(W,H-380+y)], fill=(0,0,0,a))

    # Üst gradient — sadece başlık için ince
    for y in range(180):
        a = int(150 * ease_out(1-y/180) * alpha)
        draw.line([(0,y),(W,y)], fill=(0,0,0,a))

    # Accent çizgi alt
    bw = int(W * alpha)
    draw.rectangle([(W-bw)//2, H-6, (W+bw)//2, H], fill=(*ac,int(255*alpha)))

    # İlerleme noktaları
    sp = 30; tw = total*sp; sx = (W-tw)//2; dy = H-48
    for i in range(total):
        cx = sx+i*sp+sp//2
        if i == seg_idx:
            draw.ellipse([cx-8,dy-8,cx+8,dy+8], fill=(*ac,int(255*alpha)))
        else:
            draw.ellipse([cx-4,dy-4,cx+4,dy+4], fill=(180,180,180,int(80*alpha)))

    # Ana metin — tam ortada
    slide = int(25*(1-ease_out(t/0.4)))
    mfont = get_font(56)
    lines = wrap_text(draw, seg_text, mfont, W-100)
    lh    = int(56*1.4)
    th    = len(lines)*lh
    ty    = (H//2) - th//2 + 80 + slide

    for line in lines:
        bb = draw.textbbox((0,0),line,font=mfont)
        lw = bb[2]
        x  = (W-lw)//2
        for ox,oy in [(-4,-4),(4,-4),(-4,4),(4,4),(0,-5),(0,5),(-5,0),(5,0)]:
            draw.text((x+ox,ty+oy),line,font=mfont,fill=(0,0,0,int(230*alpha)))
        draw.text((x,ty),line,font=mfont,fill=(255,252,240,int(255*alpha)))
        ty += lh

    # Üst: başlık
    if title:
        clean = re.sub(r'[^\w\s\-\:\!\?\.\,ğüşıöçĞÜŞİÖÇ]','',title).strip()[:55]
        tf    = get_font(34)
        tlines= wrap_text(draw, clean, tf, W-120)
        ty2   = 70
        for tl in tlines[:2]:
            tb = draw.textbbox((0,0),tl,font=tf)
            tw2= tb[2]
            tx = (W-tw2)//2
            for ox,oy in [(-2,-2),(2,-2),(-2,2),(2,2)]:
                draw.text((tx+ox,ty2+oy),tl,font=tf,fill=(0,0,0,int(200*alpha)))
            draw.text((tx,ty2),tl,font=tf,fill=(255,245,200,int(230*alpha)))
            ty2 += int(34*1.35)

    # Üst sağ: dönem
    if period:
        pf   = get_font(26)
        ptxt = period.upper()
        pb   = draw.textbbox((0,0),ptxt,font=pf)
        pw   = pb[2]
        px   = W-pw-50
        draw.rounded_rectangle([px-12,38,px+pw+12,74],radius=6,
                               fill=(0,0,0,int(160*alpha)))
        draw.rounded_rectangle([px-12,38,px+pw+12,74],radius=6,
                               outline=(*ac,int(140*alpha)))
        draw.text((px,44),ptxt,font=pf,fill=(*ac,int(240*alpha)))

    result = Image.alpha_composite(img, overlay)
    return np.array(result.convert("RGB"))


# ── TTS ───────────────────────────────────────────────────────────

async def _tts_edge(text, path):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    comm = edge_tts.Communicate(text=text, voice="tr-TR-AhmetNeural", rate="+5%")
    await comm.save(path)


def generate_tts(text, path, channel="tarih"):
    """ElevenLabs ile TTS uret, hata olursa edge_tts kullan."""
    try:
        from config import ELEVENLABS_API_KEY
        if not ELEVENLABS_API_KEY:
            raise ValueError("API key yok")
        import httpx
        from elevenlabs import ElevenLabs, save
        voice_id = NOTES_VOICE_ID if channel == "notesofhistory" else "K72v6nhNPFHUbP76lOVL"
        http_client = httpx.Client(verify=False)
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY, httpx_client=http_client)
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            voice_settings={"stability": 0.72, "similarity_boost": 0.85,
                           "style": 0.30, "use_speaker_boost": True},
        )
        save(audio, path)
        print(f"    ElevenLabs TTS ({channel}): {os.path.basename(path)}")
    except Exception as e:
        print(f"    ElevenLabs hata ({e}), edge_tts kullaniliyor...")
        voice = "en-US-GuyNeural" if channel == "notesofhistory" else "tr-TR-AhmetNeural"
        async def _edge_ch(t, p, v):
            import ssl, edge_tts
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            await edge_tts.Communicate(text=t, voice=v, rate="+5%").save(p)
        asyncio.run(_edge_ch(text, path, voice))

def make_title_thumbnail(title: str, accent_hex: str = "#d97706") -> np.ndarray:
    """tarihtmblr.png uzerine baslik yazili thumbnail uretir."""
    import platform
    IS_WIN = platform.system() == "Windows"

    tmblr_paths = [
        "tarihtmblr.png",
        "/app/tarihtmblr.png",
        r"C:\Users\yusuf.bas\youtube_agent\tarihtmblr.png" if IS_WIN else "/app/tarihtmblr.png",
    ]

    bg = None
    for p in tmblr_paths:
        if os.path.exists(p):
            try:
                bg = Image.open(p).convert("RGB")
                bg = bg.resize((W, H), Image.LANCZOS)
                print(f"  thumbnail: {p}")
                break
            except: pass

    if bg is None:
        bg = Image.new("RGB", (W, H), (8, 5, 2))
        draw_bg = ImageDraw.Draw(bg)
        for y in range(H):
            t = y / H
            draw_bg.line([(0,y),(W,y)], fill=(int(8+20*t), int(5+10*t), int(2+5*t)))

    draw = ImageDraw.Draw(bg)

    # Baslik temizle
    import re as _re
    clean_title = _re.sub(r"[^\w\s\-\:\.\!\?\,]", "", title, flags=_re.UNICODE).strip()
    if not clean_title:
        clean_title = title[:60]

    # Font boyutu — cok buyuk yaz ki dikkat ceksin
    fs = 96 if len(clean_title) < 20 else 82 if len(clean_title) < 35 else 68 if len(clean_title) < 50 else 58
    tf = get_font(fs)

    # Kelime wrap — daire genisligine gore (W-120)
    words = clean_title.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textbbox((0,0), test, font=tf)[2] > W-120 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)

    lh = int(fs * 1.35)
    total_h = len(lines) * lh
    # tarihtmblr.png'de dairenin merkezi gorsel yuksekliginin %42'sinde
    # Yaziyi dairenin icine ortala
    center_y = int(H * 0.47)  # Dairenin merkezi — tarihtmblr.png için kalibre edildi
    ty = center_y - total_h // 2

    for line in lines:
        bb = draw.textbbox((0,0), line, font=tf)
        lw2 = bb[2]
        x = (W - lw2) // 2
        # Kalin siyah dis golge — okunabilirligi arttirir
        for ox, oy in [(-6,-6),(6,-6),(-6,6),(6,6),(0,-8),(0,8),(-8,0),(8,0),
                       (-4,-4),(4,-4),(-4,4),(4,4)]:
            draw.text((x+ox, ty+oy), line, font=tf, fill=(5,3,0,255))
        # Kahverengi/siyah ic golge
        for ox, oy in [(-2,-2),(2,-2),(-2,2),(2,2)]:
            draw.text((x+ox, ty+oy), line, font=tf, fill=(40,20,5,255))
        # Altin sari ana yazi — parlak ve goz alici
        draw.text((x, ty), line, font=tf, fill=(255,220,80,255))
        ty += lh

    return np.array(bg)

def make_logo_clip(duration: float, fade_out: bool = False,
                   title: str = "", accent_hex: str = "#d97706") -> VideoClip:
    """Giris klibi — tarihtmblr.png + baslik yazisi, logo yok."""
    try:
        thumb = make_title_thumbnail(title, accent_hex) if title else None
    except Exception as e:
        print(f"  Thumbnail hata: {e}")
        thumb = None

    # Fallback: siyah
    fallback = np.zeros((H, W, 3), dtype=np.uint8)
    frame_arr = thumb if thumb is not None else fallback

    def make_frame(t):
        frame = frame_arr.copy()
        if t < 0.4:
            alpha = t / 0.4
        elif fade_out and t > duration - 0.4:
            alpha = (duration - t) / 0.4
        else:
            alpha = 1.0
        alpha = max(0.0, min(1.0, alpha))
        return (frame * alpha).astype(np.uint8)

    return VideoClip(make_frame, duration=duration)


def create_history_video(content: dict, output_path: str = None, channel: str = "tarih") -> str:
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if channel == "notesofhistory":
            output_path = f"output/notesofhistory/notes_{ts}.mp4"
        else:
            output_path = f"output/tarih/tarih_{ts}.mp4"

    out_dir = NOTES_OUTPUT_DIR if channel == "notesofhistory" else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    title      = content.get("title","")
    segments   = content.get("segments",[])[:6]
    narration  = content.get("full_narration", title)
    period     = content.get("period","")
    accent_hex = content.get("accent_color","#d97706")
    pexels_q   = content.get("pexels_queries",[])

    print(f"\n  🎬 {title[:55]}")

    # Görsel arama terimleri
    if not pexels_q:
        topic = content.get("topic", title)
        pexels_q = [
            f"{topic} dramatic cinematic",
            f"{period} historic dramatic",
            "ancient empire dramatic dark",
            "history battle cinematic",
            "dramatic moody landscape",
        ]

    # Görselleri indir — her sorgu için farklı resim al
    print(f"  🔍 Görseller aranıyor ({len(pexels_q)} sorgu)...")
    import random as _random
    # Sorguları karıştır — her çalıştırmada farklı sıra
    shuffled_q = pexels_q.copy()
    _random.shuffle(shuffled_q)
    # Her segment için farklı arama yap
    urls = fetch_images(shuffled_q, count=len(segments)+3)
    # URL'leri de karıştır — aynı sırayı önle
    _random.shuffle(urls)
    images = []
    for url in urls:
        img = download_image(url)
        if img:
            img = prepare_for_shorts(img)
            img = make_dramatic(img)
            images.append(img)
            if len(images) >= len(segments):
                break

    # Eksik görselleri fallback ile tamamla
    idx = 0
    while len(images) < len(segments):
        images.append(make_fallback_image(accent_hex, idx))
        idx += 1

    print(f"  → {len(images)} görsel hazır ({sum(1 for u in urls if u)} URL bulunmuştu)")

    # Giriş TTS: "Tarihten Notlar"
    print(f"  🎙 Giriş sesi...")
    intro_tts_path = output_path.replace(".mp4","_intro_tts.mp3")
    intro_text = "Notes of History" if channel == "notesofhistory" else "Tarihten Notlar"
    generate_tts(intro_text, intro_tts_path, channel=channel)
    intro_audio = AudioFileClip(intro_tts_path)
    intro_dur   = max(intro_audio.duration + 0.8, 2.5)

    # ── TTS: Her segment için ayrı ses üret (görsel-ses senkronu) ──
    print(f"  🎙 Segment seslendirmeleri...")
    seg_audio_clips = []
    seg_durations   = []
    seg_tts_paths   = []

    for i, seg in enumerate(segments):
        seg_text = seg.get("narration") or seg.get("text","")
        if not seg_text.strip():
            seg_text = narration  # fallback
        tts_p = output_path.replace(".mp4", f"_seg{i}_tts.mp3")
        seg_tts_paths.append(tts_p)
        generate_tts(seg_text, tts_p, channel=channel)
        aclip = AudioFileClip(tts_p)
        # Segment süresi = TTS süresi + 0.6s nefes payı, min 3s
        sd = max(3.0, aclip.duration + 0.6)
        seg_audio_clips.append(aclip)
        seg_durations.append(sd)
        print(f"    Seg {i+1}: {sd:.1f}s ({aclip.duration:.1f}s TTS)")

    total_dur = sum(seg_durations)
    print(f"  ⏱ Toplam içerik: {total_dur:.1f}s, {len(segments)} segment")

    # Klipleri üret (her segment kendi süresinde)
    dirs  = ["center","left","right","up","down","center"]
    clips = []
    for i, seg in enumerate(segments):
        # Seedance 2.0 varsa AI video dene, yoksa Pixabay görsel kullan
        ai_frame = pick_ai_video_clip(
            visual_desc=seg.get("visual",""),
            topic=content.get("topic", title),
            period=period,
            seg_idx=i, total=len(segments)
        )
        img_arr   = ai_frame if ai_frame is not None else np.array(images[i])
        zoom_in   = (i % 2 == 0) if ai_frame is None else False
        direction = dirs[i % len(dirs)]
        seg_text  = seg.get("text","")
        show_hdr  = (i == 0)
        sd        = seg_durations[i]

        def make_frame(t, _img=img_arr,
                       _txt=seg.get("narration") or seg.get("text",""),
                       _sd=sd, _zi=zoom_in, _dir=direction, _i=i, _sh=show_hdr):
            frame = ken_burns(Image.fromarray(_img), t, _sd, _zi, _dir)
            return add_overlay(
                frame, t, _txt, _sd, accent_hex,
                title=title if _sh else "",
                period=period if _sh else "",
                seg_idx=_i, total=len(segments)
            )

        # Ses: 0.3s gecikmeyle başlat, segmentin kendi TTS'i
        # Audio: 0.3s gecikmeli başlat, sona 0.3s fade out ekle
        _aclip = seg_audio_clips[i]
        # Ses süresi video süresini aşmasın, 0.5s fade out ile yumuşat
        fade_dur = min(0.5, _aclip.duration * 0.15)
        _aclip_faded = _aclip.audio_fadeout(fade_dur).audio_fadein(0.1)
        # set_end kaldırıldı — ses kendi doğal süresinde biter
        seg_audio = _aclip_faded.set_start(0.2)
        vc = VideoClip(make_frame, duration=sd).set_audio(seg_audio)
        clips.append(vc)

    # Giriş ve çıkış logo klipleri
    intro_clip = make_logo_clip(intro_dur, fade_out=False, title=title, accent_hex=accent_hex)
    # Outro clip — kanal bazlı
    import platform
    IS_WIN = platform.system() == "Windows"
    if channel == "notesofhistory":
        notes_outro = NOTES_OUTRO_PATH_WIN if IS_WIN else NOTES_OUTRO_PATH_LIN
        if os.path.exists(notes_outro):
            try:
                outro_img = Image.open(notes_outro).convert("RGB").resize((W,H), Image.LANCZOS)
                outro_arr = np.array(outro_img)
                def _outro_frame(t):
                    a = max(0.0, min(1.0, (2.5-t)/0.5))
                    return (outro_arr * a).astype(np.uint8)
                outro_clip = VideoClip(_outro_frame, duration=2.5)
            except:
                outro_clip = make_logo_clip(2.5, fade_out=True, title="", accent_hex=accent_hex)
        else:
            outro_clip = make_logo_clip(2.5, fade_out=True, title="", accent_hex=accent_hex)
    else:
        outro_clip = make_logo_clip(2.5, fade_out=True, title="", accent_hex=accent_hex)

    # Giriş ses + intro klibi (fade out ile)
    intro_audio_end = min(intro_dur, intro_audio.duration + 0.3)
    intro_audio_faded = intro_audio.audio_fadeout(0.3)
    intro_clip = intro_clip.set_audio(
        intro_audio_faded.set_start(0.3).set_end(intro_audio_end)
    )

    content_clip = concatenate_videoclips(clips, method="chain")
    final = concatenate_videoclips([intro_clip, content_clip, outro_clip], method="chain")
    full_dur = intro_dur + total_dur + 2.5

    # Müzik: sadece telif-free (royalty-free) müzik kullan
    # Telif sorununu önlemek için müzik klasöründeki dosyalar
    # mutlaka royalty-free olmalı (freemusicarchive.org, pixabay music vb.)
    try:
        from music_manager import find_music_by_keywords, get_fallback_music
        music_path = find_music_by_keywords(["ozlu","epik","huzur","yasam","felsefe"])
        if not music_path: music_path = get_fallback_music()
        if music_path and os.path.exists(music_path):
            music = AudioFileClip(music_path)
            if music.duration < full_dur:
                loops = int(np.ceil(full_dur/music.duration))+1
                music = concatenate_audioclips([music]*loops)
            music = music.subclip(0, full_dur).volumex(0.08)
            existing_audio = final.audio
            if existing_audio:
                audio = CompositeAudioClip([existing_audio, music]).set_end(full_dur)
            else:
                audio = music
            final = final.set_audio(audio)
            print(f"  🎵 Müzik eklendi: {os.path.basename(music_path)}")
        else:
            print(f"  ℹ Müzik bulunamadı, sadece TTS kullanılıyor")
    except Exception as e:
        print(f"  ⚠ Müzik: {e}")

    # Üretim tarihi/saati damgası — sol alt köşe
    generated_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    print(f"  💾 Kaydediliyor (~{max(1,int(full_dur*FPS/180))} dk)...")
    final.write_videofile(
        output_path, fps=FPS,
        codec="libx264", audio_codec="aac",
        logger=None, threads=8,
        preset="ultrafast",
        ffmpeg_params=["-crf","26"]
    )

    # Temp ses dosyalarını temizle
    for f in [intro_tts_path] + seg_tts_paths:
        try: os.remove(f)
        except: pass

    # Hashtag genişletildi
    base_tags = content.get("tags",[])
    extra_tags = ["tarih","tarihtennotlar","shorts","keşfet","belgesel",
                  "osmanlı","türkiye","dünyatarihi","tarihigerçekler",
                  "ilginçtarih","shorts","viral","keşfetteyim"]
    all_tags = list(dict.fromkeys(base_tags + extra_tags))[:30]

    base_hashtags = content.get("hashtags",[])
    extra_hashtags = ["#tarih","#tarihtennotlar","#shorts","#keşfet",
                      "#belgesel","#osmanlı","#dünyatarihi","#tarihigerçekler",
                      "#ilginçtarih","#viral","#keşfetteyim","#bilgi"]
    all_hashtags = list(dict.fromkeys(base_hashtags + extra_hashtags))[:15]

    meta = {
        "title":        content.get("title",""),
        "description":  content.get("description","") + "\n\n" + " ".join(all_hashtags),
        "tags":         all_tags,
        "hashtags":     all_hashtags,
        "topic":        content.get("topic",""),
        "period":       content.get("period",""),
        "format":       content.get("format","timeline"),
        "channel":      channel,
        "generated_at": generated_str,
    }
    with open(output_path.replace(".mp4",".json"),"w",encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    mb = os.path.getsize(output_path)/(1024*1024)
    print(f"  ✅ Hazır: {output_path} ({mb:.1f} MB) — {generated_str}")
    return output_path


if __name__ == "__main__":
    from history_content_generator import generate_history_content, get_best_format
    content = generate_history_content(format_type=get_best_format())
    print(f"Konu: {content['title']}")
    create_history_video(content)
