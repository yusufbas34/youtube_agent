"""
AI Video Generator — BytePlus ModelArk Seedance 2.0
Tarih kanalı için segment bazlı video üretir.
Kurulum: pip install byteplus-python-sdk-v2
"""

import os, time, requests, json
from pathlib import Path

TMP_DIR = Path("/tmp/ai_video")
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Model seçimi — önce Fast (daha ucuz), kalite için Standard
MODEL_FAST     = "seedance-1-5-pro-251215"  # Aktif model ID
MODEL_STANDARD = "seedance-1-5-pro-251215"  # Aktif model ID

BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"


def get_ark_client():
    """BytePlus Ark client oluştur."""
    # Railway'de BYTEPLUS_API_KEY veya ARK_API_KEY olarak eklenebilir
    api_key = (os.environ.get("BYTEPLUS_API_KEY","") or
               os.environ.get("ARK_API_KEY",""))
    if not api_key:
        try:
            from config import BYTEPLUS_API_KEY
            api_key = BYTEPLUS_API_KEY
        except: pass
    if not api_key:
        raise ValueError("BYTEPLUS_API_KEY eksik")
    try:
        from byteplussdkarkruntime import Ark
        return Ark(base_url=BASE_URL, api_key=api_key)  # ARK_API_KEY or BYTEPLUS_API_KEY
    except ImportError:
        raise ImportError("pip install byteplus-python-sdk-v2")


def generate_segment_video(prompt: str, duration: int = 5,
                           aspect_ratio: str = "9:16",
                           model: str = MODEL_FAST,
                           output_path: str = None) -> str | None:
    """
    Tek bir segment için AI video üretir.
    - prompt: sahne açıklaması (İngilizce en iyi sonuç verir)
    - duration: 5 veya 10 saniye
    - aspect_ratio: "9:16" (Shorts için)
    - output_path: kaydedilecek dosya
    Döner: video dosya yolu veya None
    """
    api_key = (os.environ.get("BYTEPLUS_API_KEY","") or
               os.environ.get("ARK_API_KEY",""))
    if not api_key:
        try:
            from config import BYTEPLUS_API_KEY; api_key = BYTEPLUS_API_KEY
        except: pass
    if not api_key:
        print("  ⚠ BYTEPLUS_API_KEY/ARK_API_KEY yok, Seedance atlanıyor")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Video üretim görevi oluştur
    payload = {
        "model": model,
        "content": [
            {
                "type": "text",
                "text": f"{prompt} --ratio {aspect_ratio} --resolution 720p --duration {duration}",
            }
        ]
    }

    try:
        print(f"  🎬 AI video üretiliyor: {prompt[:60]}...")
        r = requests.post(
            f"{BASE_URL}/content_generation/tasks",
            headers=headers, json=payload, timeout=30, verify=False
        )
        if r.status_code != 200:
            print(f"  ⚠ Seedance API hatası: {r.status_code} — {r.text[:150]}")
            return None

        task_id = r.json().get("id")
        if not task_id:
            print(f"  ⚠ Task ID alınamadı: {r.text[:100]}")
            return None

        print(f"  ⏳ Task başladı: {task_id}")

        # Polling — max 5 dakika
        for attempt in range(30):
            time.sleep(10)
            pr = requests.get(
                f"{BASE_URL}/content_generation/tasks/{task_id}",
                headers=headers, timeout=15, verify=False
            )
            if pr.status_code != 200:
                continue
            data = pr.json()
            status = data.get("status", "")
            print(f"  → Durum: {status} ({attempt+1}/30)")

            if status == "succeeded":
                # Video URL'sini al
                video_url = None
                for item in data.get("content", []):
                    if item.get("type") == "video_url":
                        video_url = item.get("url") or item.get("video_url")
                        break
                if not video_url:
                    # Farklı format dene
                    video_url = data.get("video_url") or data.get("output", {}).get("video_url")

                if not video_url:
                    print(f"  ⚠ Video URL bulunamadı: {json.dumps(data)[:200]}")
                    return None

                # İndir
                if not output_path:
                    output_path = str(TMP_DIR / f"seg_{int(time.time())}.mp4")

                vr = requests.get(video_url, timeout=60, verify=False)
                with open(output_path, "wb") as f:
                    f.write(vr.content)
                size = os.path.getsize(output_path) // 1024
                print(f"  ✅ AI video hazır: {output_path} ({size}KB)")
                return output_path

            elif status == "failed":
                print(f"  ❌ Seedance başarısız: {data.get('error','?')}")
                return None

        print("  ❌ Seedance timeout (5 dk)")
        return None

    except Exception as e:
        print(f"  ⚠ Seedance hatası: {e}")
        return None


def generate_history_ai_clips(content: dict, output_dir: str) -> list[str]:
    """
    Tarih içeriğindeki her segment için AI video klibi üretir.
    Döner: video dosya yolları listesi
    """
    segments = content.get("segments", [])
    clips = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for i, seg in enumerate(segments):
        # Her segment için sinematik prompt oluştur
        visual_desc = seg.get("visual", "")
        topic = content.get("topic", content.get("title", "history"))
        period = content.get("period", "")

        # Tarih videosu için prompt
        prompt = build_history_prompt(
            visual=visual_desc,
            topic=topic,
            period=period,
            segment_idx=i,
            total=len(segments)
        )

        out = os.path.join(output_dir, f"clip_{i:02d}.mp4")
        clip = generate_segment_video(
            prompt=prompt,
            duration=5,
            aspect_ratio="9:16",
            model=MODEL_FAST,
            output_path=out
        )
        if clip:
            clips.append(clip)
        else:
            # Fallback: Pixabay'den al
            print(f"  → Segment {i} için Pixabay fallback")
            clips.append(None)  # None = Pixabay kullan

    return clips


def build_history_prompt(visual: str, topic: str, period: str,
                         segment_idx: int, total: int) -> str:
    """Tarih videosu için sinematik Seedance prompt'u oluşturur."""
    # Kamera hareketleri — farklı segmentler için farklı
    cameras = [
        "dramatic slow zoom in, golden hour lighting",
        "cinematic tracking shot, atmospheric fog",
        "epic wide angle reveal, dramatic shadows",
        "slow motion close up, dust particles in air",
        "aerial drone shot pulling back, sweeping landscape",
        "handheld documentary style, gritty realism",
    ]
    camera = cameras[segment_idx % len(cameras)]

    # Stil
    style = "epic historical documentary style, cinematic color grading, film grain, 4K"

    if visual:
        prompt = f"{visual}, {camera}, {style}"
    else:
        prompt = f"Historical scene depicting {topic}, {period} era, {camera}, {style}"

    return prompt


def is_seedance_available() -> bool:
    """BytePlus API key mevcut mu kontrol et."""
    key = (os.environ.get("BYTEPLUS_API_KEY","") or
            os.environ.get("ARK_API_KEY",""))
    if not key:
        try:
            from config import BYTEPLUS_API_KEY; key = BYTEPLUS_API_KEY
        except: pass
    return bool(key)


if __name__ == "__main__":
    # Test
    print("Seedance 2.0 test...")
    if not is_seedance_available():
        print("BYTEPLUS_API_KEY eksik. Railway'e ekle.")
    else:
        clip = generate_segment_video(
            prompt="Ancient Roman soldiers marching through cobblestone streets, torches burning, epic cinematic shot",
            duration=5,
            output_path="/tmp/test_seedance.mp4"
        )
        print("Sonuç:", clip)
