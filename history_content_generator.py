"""
Tarih Kanalı İçerik Üreticisi
Claude API ile tarihsel içerik üretir, başarısız olursa Gemini kullanır.
"""

import json, os, re
from datetime import datetime


def get_client():
    import httpx
    from config import ANTHROPIC_API_KEY
    import anthropic
    http = httpx.Client(verify=False)
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)


def get_best_format(analytics_data: dict = None) -> str:
    from channel_config import HISTORY_VIDEO_FORMATS
    if not analytics_data:
        return "timeline"
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


def build_prompt(topic, format_type, today):
    topic_prompt = f'Konu: "{topic}"' if topic else f"Bugün ({today}) yaşanan tarihi bir olay veya ilginç tarih konusu. Titanik veya çok bilinen olaylar KULLANMA, daha az bilinen ama ilginç konular seç."
    format_descriptions = {
        "timeline":    "Kronolojik sırayla gelişen olaylar (başlangıç → gelişme → sonuç)",
        "illustrated": "Tek bir olay veya kişi hakkında derin anlatım",
        "map":         "Coğrafi konumu olan bir olay veya savaş/keşif",
        "simple":      "Kısa ve çarpıcı tarih bilgisi",
    }
    fmt_desc = format_descriptions.get(format_type, format_descriptions["timeline"])
    return f"""
Sen YouTube Shorts için Türkçe tarih videoları üreten bir içerik üreticisisin.

{topic_prompt}

Video formatı: {fmt_desc}

ÖNEMLİ: Her seferinde FARKLI ve AZ BİLİNEN bir konu seç. Titanik, Fatih Sultan Mehmet gibi çok işlenmiş konulardan kaçın.

Sadece JSON döndür (başka hiçbir şey yazma):
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
  "tags": ["tarih", "shorts", "ilginç"],
  "hashtags": ["#tarih", "#shorts", "#ilginçbilgiler"],
  "topic": "konu adı",
  "period": "dönem (örn: Osmanlı, Roma, Modern)",
  "format": "{format_type}",
  "background_color": "#1a0a05",
  "accent_color": "#d97706",
  "pexels_queries": [
    "exact visual query 1 matching the story in english",
    "exact visual query 2 matching the period in english",
    "dramatic atmospheric backup query in english"
  ]
}}"""


def parse_response(text):
    if "```json" in text: text = text.split("```json")[1].split("```")[0]
    elif "```" in text:   text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def generate_with_claude(prompt):
    client = get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()


def generate_with_gemini(prompt):
    """Gemini API ile içerik üretir."""
    try:
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if not gemini_key:
            try:
                from config import GEMINI_API_KEY
                gemini_key = GEMINI_API_KEY
            except: pass
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY bulunamadı")

        import requests, httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 3000, "temperature": 0.9}
        }
        r = requests.post(url, json=body, timeout=30, verify=False)
        if r.status_code != 200:
            raise Exception(f"Gemini HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        raise Exception(f"Gemini hata: {e}")


def generate_history_content(topic: str = None, format_type: str = "timeline") -> dict:
    today  = datetime.now().strftime("%d %B")
    prompt = build_prompt(topic, format_type, today)

    # 1. Claude dene
    text = None
    try:
        print("  → Claude ile içerik üretiliyor...")
        text = generate_with_claude(prompt)
        print("  ✅ Claude başarılı")
    except Exception as e:
        print(f"  ⚠ Claude hata: {e}")
        print("  → Gemini'ye geçiliyor...")
        try:
            text = generate_with_gemini(prompt)
            print("  ✅ Gemini başarılı")
        except Exception as e2:
            raise Exception(f"Claude ve Gemini ikisi de başarısız: {e} | {e2}")

    content = parse_response(text)
    content["format"]       = format_type
    content["generated_at"] = datetime.now().isoformat()
    return content


def update_format_analytics(format_type: str, views: int, likes: int):
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
