"""
D-ID API Test Modulu
Tarih kanalı için konuşan avatar videosu üretir.
Test amaçlı — normal sistemi etkilemez.
"""

import os, requests, time, json
from pathlib import Path

DID_API_URL = "https://api.d-id.com"
TMP_DIR = Path("/tmp/did_test")
TMP_DIR.mkdir(parents=True, exist_ok=True)


def get_api_key():
    key = os.environ.get("DID_API_KEY", "")
    if not key:
        try:
            from config import DID_API_KEY
            key = DID_API_KEY
        except: pass
    return key


def get_available_presenters(api_key: str) -> list:
    """Kullanılabilir avatar listesini çek."""
    try:
        r = requests.get(
            f"{DID_API_URL}/presenters",
            headers={"Authorization": f"Basic {api_key}",
                     "Content-Type": "application/json"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json().get("presenters", [])
        print(f"  ⚠ Presenters: {r.status_code} — {r.text[:100]}")
    except Exception as e:
        print(f"  ⚠ Presenters hatasi: {e}")
    return []


def create_talking_avatar(
    text: str,
    audio_path: str = None,
    presenter_id: str = None,
    output_path: str = None,
    api_key: str = None
) -> str | None:
    """
    D-ID ile konuşan avatar videosu üretir.
    text: konuşma metni (TTS için)
    audio_path: hazır ses dosyası (varsa text yerine kullanılır)
    presenter_id: avatar ID (None ise varsayılan)
    output_path: çıktı dosyası
    Döner: video dosya yolu veya None
    """
    if not api_key:
        api_key = get_api_key()
    if not api_key:
        print("  ⚠ DID_API_KEY eksik")
        return None

    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }

    # Ses kaynağı
    if audio_path and os.path.exists(audio_path):
        # Ses dosyasını base64'e çevir
        import base64
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()
        audio_payload = {
            "type": "base64",
            "encoding": "mp3",
            "audio": audio_b64,
        }
        script = {"type": "audio", "audio_url": None}
        # D-ID audio upload
        upload_r = requests.post(
            f"{DID_API_URL}/audios",
            headers=headers,
            json={"audio": audio_b64, "encoding": "mp3"},
            timeout=30
        )
        if upload_r.status_code == 201:
            audio_url = upload_r.json().get("url")
            script = {"type": "audio", "audio_url": audio_url}
        else:
            # text TTS'e düş
            script = {"type": "text", "input": text,
                     "provider": {"type": "microsoft",
                                  "voice_id": "tr-TR-AhmetNeural"}}
    else:
        # Text → D-ID TTS
        script = {
            "type": "text",
            "input": text[:500],  # D-ID max 500 char
            "provider": {
                "type": "microsoft",
                "voice_id": "tr-TR-AhmetNeural"
            }
        }

    # Avatar seç
    source_url = None
    if presenter_id:
        source_url = f"presenter_id:{presenter_id}"

    # Talk isteği
    payload = {
        "script": script,
        "config": {"fluent": True, "pad_audio": 0.0},
    }

    if presenter_id:
        payload["presenter_id"] = presenter_id
    else:
        # Varsayılan avatar — D-ID stock görsel
        payload["source_url"] = "https://create-images-results.d-id.com/DefaultPresenters/Noelle_f/image.jpeg"

    print(f"  🎭 D-ID avatar video üretiliyor...")
    try:
        r = requests.post(
            f"{DID_API_URL}/talks",
            headers=headers,
            json=payload,
            timeout=30
        )
        print(f"  → Talk isteği: {r.status_code} — {r.text[:500]}")
        if r.status_code not in (200, 201):
            print(f"  ❌ D-ID hata: {r.text[:500]}")
            return None

        talk_id = r.json().get("id")
        if not talk_id:
            print(f"  ❌ Talk ID alınamadı")
            return None

        print(f"  ⏳ Talk ID: {talk_id} — işleniyor...")

        # Poll — max 3 dakika
        for attempt in range(18):
            time.sleep(10)
            pr = requests.get(
                f"{DID_API_URL}/talks/{talk_id}",
                headers=headers,
                timeout=15
            )
            if pr.status_code == 200:
                data = pr.json()
                status = data.get("status")
                print(f"  → Durum: {status} ({attempt+1}/18)")
                if status == "done":
                    video_url = data.get("result_url")
                    if not video_url:
                        print("  ❌ Video URL yok")
                        return None
                    # İndir
                    if not output_path:
                        output_path = str(TMP_DIR / f"did_{talk_id}.mp4")
                    vr = requests.get(video_url, timeout=60)
                    with open(output_path, "wb") as f:
                        f.write(vr.content)
                    sz = os.path.getsize(output_path) // 1024
                    print(f"  ✅ D-ID video hazır: {output_path} ({sz}KB)")
                    return output_path
                elif status == "error":
                    print(f"  ❌ D-ID işlem hatası: {data.get('error','?')}")
                    return None

        print("  ❌ D-ID timeout")
        return None

    except Exception as e:
        print(f"  ❌ D-ID exception: {e}")
        return None


def test_did_api() -> dict:
    """D-ID API'yi test et ve sonucu döndür."""
    api_key = get_api_key()
    if not api_key:
        return {"ok": False, "error": "DID_API_KEY eksik"}

    # Kısa test metni
    test_text = "Merhaba! Ben tarih kanalınızın yapay zeka sunucusuyum. Bugün size tarihin en gizemli sırlarından birini anlatacağım."

    print("\n=== D-ID API TEST ===")
    print(f"API Key: {api_key[:10]}...")

    # Presenters listesi
    presenters = get_available_presenters(api_key)
    print(f"Kullanılabilir avatar sayısı: {len(presenters)}")

    # Video üret
    out = str(TMP_DIR / "did_test_output.mp4")
    result = create_talking_avatar(
        text=test_text,
        output_path=out,
        api_key=api_key
    )

    if result:
        sz = os.path.getsize(result) // 1024
        return {
            "ok": True,
            "video_path": result,
            "video_url": f"/tmp/did_test/{os.path.basename(result)}",
            "size_kb": sz,
            "presenters": len(presenters),
            "message": f"✅ D-ID test başarılı! {sz}KB video üretildi."
        }
    else:
        return {"ok": False, "error": "Video üretilemedi"}


if __name__ == "__main__":
    result = test_did_api()
    print(json.dumps(result, ensure_ascii=False, indent=2))
