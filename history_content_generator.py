"""
Tarih Kanalı İçerik Üreticisi
Claude API ile tarihsel içerik üretir.
YouTube analytics verilerine göre en çok izlenen formatı seçer.
"""

import json, os
from datetime import datetime
import anthropic, httpx
from config import ANTHROPIC_API_KEY


def get_client():
    http = httpx.Client(verify=False)
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)


def get_best_format(analytics_data: dict = None) -> str:
    """
    YouTube analytics'e göre en çok izlenen formatı döner.
    Veri yoksa dengeli başlar, zamanla öğrenir.
    """
    from channel_config import HISTORY_VIDEO_FORMATS

    if not analytics_data:
        # Analytics yoksa başlangıçta hepsini dene
        return "timeline"

    # Her formatın ortalama izlenme sayısını hesapla
    format_views = {}
    for fmt, data in analytics_data.get("formats", {}).items():
        views = data.get("total_views", 0)
        count = data.get("video_count", 1)
        format_views[fmt] = views / count if count > 0 else 0

    if not format_views:
        return "timeline"

    best = max(format_views, key=format_views.get)
    print(f"  → En iyi format: {best} ({format_views[best]:.0f} ort. izlenme)")
    return best


def generate_history_content(topic: str = None, format_type: str = "timeline") -> dict:
    """
    Claude ile tarih videosu içeriği üretir.
    """
    client = get_client()

    today = datetime.now().strftime("%d %B")

    topic_prompt = f'Konu: "{topic}"' if topic else f"Bugün ({today}) yaşanan tarihi bir olay veya ilginç tarih konusu"

    format_descriptions = {
        "timeline":    "Kronolojik sırayla gelişen olaylar (başlangıç → gelişme → sonuç)",
        "illustrated": "Tek bir olay veya kişi hakkında derin anlatım",
        "map":         "Coğrafi konumu olan bir olay veya savaş/keşif",
        "simple":      "Kısa ve çarpıcı tarih bilgisi",
    }
    fmt_desc = format_descriptions.get(format_type, format_descriptions["timeline"])

    prompt = f"""
Sen YouTube Shorts için Türkçe tarih videoları üreten bir içerik üreticisisin.

{topic_prompt}

Video formatı: {fmt_desc}

Çarpıcı, ilgi çekici, merak uyandıran bir tarih videosu için içerik üret.
Hedef kitle: 18-35 yaş, Türkçe konuşan, tarihe meraklı.

Sadece JSON döndür:
{{
  "title": "Video başlığı (max 90 karakter, merak uyandıran, emoji ile)",
  "hook": "İlk 3 saniye - izleyiciyi bağlayacak giriş cümlesi",
  "segments": [
    {{"time": "0-3s",  "text": "Hook cümlesi", "visual": "görsel açıklaması"}},
    {{"time": "3-8s",  "text": "Konu girişi",   "visual": "görsel açıklaması"}},
    {{"time": "8-20s", "text": "Ana içerik",    "visual": "görsel açıklaması"}},
    {{"time": "20-30s","text": "Detay/gelişme", "visual": "görsel açıklaması"}},
    {{"time": "30-45s","text": "Sonuç/etki",    "visual": "görsel açıklaması"}},
    {{"time": "45-55s","text": "İlginç detay",  "visual": "görsel açıklaması"}},
    {{"time": "55-60s","text": "CTA + kapanış", "visual": "görsel açıklaması"}}
  ],
  "full_narration": "Tam anlatım metni (TTS için, 200-280 kelime)",
  "description": "YouTube açıklaması (200-300 karakter)",
  "tags": ["tarih", "shorts", "ilginç", ...],
  "hashtags": ["#tarih", "#shorts", "#ilginçbilgiler"],
  "topic": "konu adı",
  "period": "dönem (örn: Osmanlı, Roma, Modern)",
  "format": "{format_type}",
  "background_color": "#1a0a05",
  "accent_color": "#d97706",
  "map_location": "varsa ülke/bölge adı (harita formatı için)",
  "year_range": "varsa yıl aralığı (örn: 1453-1481)",
  "pexels_queries": [
    "exact visual query 1 matching the story",
    "exact visual query 2 matching the period",
    "dramatic atmospheric backup query"
  ]
}}

pexels_queries için KURALLAR:
- İngilizce olmalı
- Konuya ve döneme ÖZEL olmalı (genel değil)
- Atmosferik, dramatik, sinematik terimler ekle
- Örnekler:
  * Osmanlı savaşı → "ottoman empire battlefield soldiers", "medieval siege castle dramatic"
  * Van Gogh → "impressionist painting sunflowers artistic", "artist studio oil painting dramatic"
  * Vietnam savaşı → "vietnam war jungle soldiers smoke", "war helicopter dramatic cinematic"
  * Roma → "ancient rome colosseum dramatic", "roman soldiers battle epic"
  * WW2 → "world war 2 battlefield dramatic", "military soldiers cinematic dark"
  * Keşif → "explorer ship ocean dramatic", "ancient map expedition cinematic"
"""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = msg.content[0].text.strip()
    if "```json" in text: text = text.split("```json")[1].split("```")[0]
    elif "```" in text:   text = text.split("```")[1].split("```")[0]

    content = json.loads(text.strip())
    content["format"] = format_type
    content["generated_at"] = datetime.now().isoformat()
    return content


def update_format_analytics(format_type: str, views: int, likes: int):
    """
    Video yüklendikten sonra analytics'i günceller.
    Sistem zamanla hangi formatın daha iyi çalıştığını öğrenir.
    """
    analytics_file = "data/tarih_analytics.json"
    os.makedirs("data", exist_ok=True)

    analytics = {}
    if os.path.exists(analytics_file):
        with open(analytics_file, "r", encoding="utf-8") as f:
            analytics = json.load(f)

    if "formats" not in analytics:
        analytics["formats"] = {}

    if format_type not in analytics["formats"]:
        analytics["formats"][format_type] = {"total_views": 0, "total_likes": 0, "video_count": 0}

    analytics["formats"][format_type]["total_views"]  += views
    analytics["formats"][format_type]["total_likes"]  += likes
    analytics["formats"][format_type]["video_count"]  += 1
    analytics["formats"][format_type]["last_updated"]  = datetime.now().isoformat()

    with open(analytics_file, "w", encoding="utf-8") as f:
        json.dump(analytics, f, ensure_ascii=False, indent=2)

    print(f"  ✅ Analytics güncellendi: {format_type} → {views} izlenme")


if __name__ == "__main__":
    print("Test: Tarih içeriği üretiliyor...")
    content = generate_history_content(format_type="timeline")
    print(f"Başlık: {content['title']}")
    print(f"Hook: {content['hook']}")
    print(f"Segment sayısı: {len(content['segments'])}")
