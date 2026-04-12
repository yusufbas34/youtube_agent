"""
Modül 2: İçerik Planlama ve Metadata Üretimi
Claude API ile senaryo, başlık, açıklama, tag ve thumbnail metni üretir.
"""

import json
import re
import anthropic
from config import (
    ANTHROPIC_API_KEY, CHANNEL_NICHE, CHANNEL_LANGUAGE,
    TARGET_AUDIENCE, VIDEO_STYLE, VIDEO_DURATION_SECONDS, MAX_TAGS
)


def generate_video_content(topic: str, suggested_title: str, trend_reason: str) -> dict:
    """
    Bir konu için tam içerik paketi üretir:
    - Kesinleşmiş başlık
    - Video senaryosu / narasyonu
    - SEO açıklaması
    - Tag listesi
    - Thumbnail için metin önerisi
    - Arama anahtar kelimeler
    """
    import ssl, httpx
    http_client = httpx.Client(verify=False)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http_client)

    duration_note = (
        "60 saniyelik YouTube Shorts formatı (çok kısa, dikkat çekici)"
        if VIDEO_STYLE == "shorts"
        else f"{VIDEO_DURATION_SECONDS // 60} dakikalık standart video"
    )

    prompt = f"""
Sen profesyonel bir YouTube içerik yazarısın. Türkçe içerik üretiyorsun.

Kanal Nişi: {CHANNEL_NICHE}
Hedef Kitle: {TARGET_AUDIENCE}
Video Formatı: {duration_note}

Konu: {topic}
Öneri Başlık: {suggested_title}
Neden Trend: {trend_reason}

Aşağıdaki formatı AYNEN kullanarak JSON üret:

{{
  "title": "kesinleşmiş başlık (emoji ile, max 70 karakter, merak uyandıran)",
  "hook": "ilk 3 saniye seyirciyi tutacak açılış cümlesi",
  "script": "tüm video narasyonu (konuşma metni, {VIDEO_DURATION_SECONDS} saniyelik içerik)",
  "description": "SEO dostu YouTube açıklaması (300-500 kelime, 3 paragraf, hashtag'siz)",
  "tags": ["tag1", "tag2", ...],
  "hashtags": ["#tag1", "#tag2", "#tag3"],
  "thumbnail_text": "thumbnail'da yazacak güçlü metin (max 4 kelime, büyük harf)",
  "thumbnail_emotion": "thumbnail için duygu yönlendirmesi (shock/joy/curiosity/fear)",
  "keywords": ["arama kelimesi 1", "arama kelimesi 2"],
  "video_prompt": "text-to-video AI için sahne açıklaması (İngilizce, görsel detaylı)"
}}

Önemli:
- Başlık merak uyandırmalı, clickbait ama dürüst olmalı
- Script doğal konuşma diline uygun olmalı
- Tag sayısı tam {MAX_TAGS} olmalı
- video_prompt sadece İngilizce, sinematik detaylarda olmalı
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    content = json.loads(response_text.strip())
    content["topic"] = topic
    content["trend_reason"] = trend_reason
    return content


def optimize_title_for_ctr(title: str) -> list[str]:
    """A/B test için başlık varyasyonları üretir."""
    import ssl, httpx
    http_client = httpx.Client(verify=False)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http_client)

    prompt = f"""
Aşağıdaki YouTube başlığı için 3 farklı varyasyon üret.
Her biri farklı bir psikolojik tetikleyici kullansın:
1. Merak/Gizem
2. Fayda/Çözüm
3. Şok/Sürpriz

Orijinal başlık: {title}

JSON formatında yanıt ver:
{{"variations": ["varyasyon1", "varyasyon2", "varyasyon3"]}}
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text
    if "```" in response_text:
        response_text = re.sub(r"```\w*", "", response_text).strip()

    result = json.loads(response_text)
    return [title] + result.get("variations", [])


def create_content_plan(trend_analysis: dict) -> dict:
    """
    Trend analizinden gelen en iyi pick için tam içerik planı oluşturur.
    """
    best_pick = trend_analysis["analysis"]["best_pick"]

    print(f"📝 İçerik planı oluşturuluyor: '{best_pick['title']}'")

    content = generate_video_content(
        topic=best_pick["topic"],
        suggested_title=best_pick["title"],
        trend_reason=best_pick["reasoning"]
    )

    # Başlık varyasyonları
    print("  → A/B başlık varyasyonları üretiliyor...")
    content["title_variations"] = optimize_title_for_ctr(content["title"])

    # Sonuçları kaydet
    with open("content_plan.json", "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    print(f"✅ İçerik planı hazır: {content['title']}")
    return content


if __name__ == "__main__":
    # Test: trend_analysis.json'dan oku
    with open("trend_analysis.json", "r", encoding="utf-8") as f:
        trend_data = json.load(f)

    plan = create_content_plan(trend_data)
    print("\n📋 İçerik Özeti:")
    print(f"  Başlık: {plan['title']}")
    print(f"  Hook: {plan['hook']}")
    print(f"  Thumbnail: {plan['thumbnail_text']}")
    print(f"  Tags ({len(plan['tags'])}): {', '.join(plan['tags'][:5])}...")
