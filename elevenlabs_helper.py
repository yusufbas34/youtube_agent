"""
ElevenLabs TTS Yardımcısı
Her kanal için özel ses ve duygu ayarları.
"""

import os, asyncio, ssl

CHANNEL_VOICE_SETTINGS = {
    "sozler": {
        "voice_id":          "t8fOU8zfPVWFYN34BllH",
        "model_id":          "eleven_multilingual_v2",
        "stability":          0.35,
        "similarity_boost":   0.80,
        "style":              0.40,
        "use_speaker_boost":  True,
    },
    "tarih": {
        "voice_id":          "NfwyWIJnRR1RrYnStGUG",
        "model_id":          "eleven_multilingual_v2",
        "stability":          0.50,
        "similarity_boost":   0.75,
        "style":              0.60,
        "use_speaker_boost":  True,
    },
    "viral": {
        "voice_id":          "8LQS4H6IYf1unP46qbKD",
        "model_id":          "eleven_multilingual_v2",
        "stability":          0.30,
        "similarity_boost":   0.85,
        "style":              0.70,
        "use_speaker_boost":  True,
    },
}


def generate_elevenlabs_tts(text: str, output_path: str, channel: str = "sozler") -> bool:
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

        print(f"  ✅ ElevenLabs TTS ({channel})")
        return True
    except Exception as e:
        print(f"  ⚠ ElevenLabs hata ({channel}): {e}")
        return False


async def _edge_tts_fallback(text: str, path: str, rate: str = "+0%"):
    import edge_tts
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    comm = edge_tts.Communicate(text=text, voice="tr-TR-EmelNeural", rate=rate)
    await comm.save(path)


def generate_tts_with_fallback(text: str, path: str, channel: str = "sozler") -> str:
    ok = generate_elevenlabs_tts(text, path, channel)
    if not ok:
        print(f"  → Edge TTS yedek ({channel})")
        rate = "+10%" if channel == "viral" else "+0%"
        asyncio.run(_edge_tts_fallback(text, path, rate))
    return path
