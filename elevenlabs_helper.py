"""
ElevenLabs TTS Yardımcısı
Her kanal için özel ses ve duygu ayarları.
"""

import os, asyncio, ssl

# Kanal ses ayarları
CHANNEL_VOICE_SETTINGS = {
    "sozler": {
        "voice_id":   "t8fOU8zfPVWFYN34BllH",
        "model_id":   "eleven_multilingual_v2",
        "stability":           0.35,  # Düşük = daha duygusal/değişken
        "similarity_boost":    0.80,
        "style":               0.40,  # Orta = hafif dramatik
        "use_speaker_boost":   True,
        "speed":               0.95,  # Biraz yavaş = düşündürücü
    },
    "tarih": {
        "voice_id":   "NfwyWIJnRR1RrYnStGUG",
        "model_id":   "eleven_multilingual_v2",
        "stability":           0.50,  # Orta = dengeli anlatıcı
        "similarity_boost":    0.75,
        "style":               0.60,  # Yüksek = dramatik anlatım
        "use_speaker_boost":   True,
        "speed":               1.00,
    },
    "viral": {
        "voice_id":   "xgYIZvUB5h2eFY3HUFNj",
        "model_id":   "eleven_multilingual_v2",
        "stability":           0.30,  # Düşük = heyecanlı/enerjik
        "similarity_boost":    0.85,
        "style":               0.70,  # Yüksek = çok dramatik/viral
        "use_speaker_boost":   True,
        "speed":               1.05,  # Biraz hızlı = canlı
    },
}


def generate_elevenlabs_tts(text: str, output_path: str, channel: str = "sozler") -> bool:
    """ElevenLabs ile TTS üretir. Başarılı olursa True döner."""
    try:
        from config import ELEVENLABS_API_KEY
        if not ELEVENLABS_API_KEY:
            return False

        import httpx
        from elevenlabs import ElevenLabs
        from elevenlabs.types import VoiceSettings

        settings = CHANNEL_VOICE_SETTINGS.get(channel, CHANNEL_VOICE_SETTINGS["sozler"])

        client = ElevenLabs(
            api_key=ELEVENLABS_API_KEY,
            httpx_client=httpx.Client(verify=False, timeout=30)
        )

        voice_settings = VoiceSettings(
            stability=settings["stability"],
            similarity_boost=settings["similarity_boost"],
            style=settings["style"],
            use_speaker_boost=settings["use_speaker_boost"],
        )

        audio = client.text_to_speech.convert(
            text=text[:500],
            voice_id=settings["voice_id"],
            model_id=settings["model_id"],
            voice_settings=voice_settings,
            output_format="mp3_44100_128",
        )

        with open(output_path, "wb") as f:
            for chunk in audio:
                if chunk:
                    f.write(chunk)

        print(f"  ✅ ElevenLabs TTS ({channel}) — style:{settings['style']} stability:{settings['stability']}")
        return True

    except Exception as e:
        print(f"  ⚠ ElevenLabs hata ({channel}): {e}")
        return False


async def _edge_tts_fallback(text: str, path: str, rate: str = "+0%"):
    """Edge TTS yedek seslendirme."""
    import edge_tts
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    comm = edge_tts.Communicate(text=text, voice="tr-TR-EmelNeural", rate=rate)
    await comm.save(path)


def generate_tts_with_fallback(text: str, path: str, channel: str = "sozler") -> str:
    """ElevenLabs dene, olmadı edge_tts kullan."""
    ok = generate_elevenlabs_tts(text, path, channel)
    if not ok:
        print(f"  → Edge TTS yedek kullanılıyor ({channel})...")
        rate = "+10%" if channel == "viral" else "+0%"
        asyncio.run(_edge_tts_fallback(text, path, rate))
    return path
