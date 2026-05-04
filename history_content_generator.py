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


def load_used_topics() -> list:
    """Daha önce kullanılmış konuları yükle."""
    try:
        path = "data/tarih_used_topics.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return []


def save_used_topic(topic: str):
    """Kullanılan konuyu kaydet."""
    try:
        path = "data/tarih_used_topics.json"
        os.makedirs("data", exist_ok=True)
        topics = load_used_topics()
        topics.append({"topic": topic, "date": datetime.now().isoformat()})
        topics = topics[-100:]  # Son 100 konu
        with open(path, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ Konu kayıt hata: {e}")


def load_youtube_uploaded_topics() -> list:
    """YouTube'a yüklenen videoların başlıklarını çeker."""
    topics = []
    try:
        hist_path = "data/tarih_history.json"
        import os as _os, json as _json
        if _os.path.exists(hist_path):
            with open(hist_path,"r",encoding="utf-8") as f:
                hist = _json.load(f)
            topics = [h.get("title","") for h in hist if h.get("title")]
    except: pass
    return topics


def build_prompt(topic, format_type, today):
    used = load_used_topics()
    used_list = ", ".join([t["topic"] for t in used[-50:]]) if used else "yok"
    yt_topics = load_youtube_uploaded_topics()
    yt_list = ", ".join(yt_topics[-30:]) if yt_topics else "yok"
    topic_prompt = f'Konu: "{topic}"' if topic else f"İlginç, az bilinen, sürpriz bir tarih konusu seç."
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

KRİTİK KURALLAR:
1. FARKLI ve AZ BİLİNEN bir konu seç — izleyiciyi şaşırtacak, "bunu bilmiyordum" dedirtecek
2. Başlık merak uyandırmalı, soru formatında veya şaşırtıcı bir iddia içermeli
3. Her segment kısa, vurucu, sinematik olmalı — belgesel anlatıcı tonu
4. narration alanı TTS için doğal konuşma dili olmalı — kısa ve etkili cümleler
5. full_narration TOPLAM 130-160 kelime olmalı (60 saniye video için kritik!)
6. Türkçe karakterleri doğru kullan: ğ, ü, ş, ı, ö, ç

Daha önce yüklediklerim (KULLANMA): {yt_list}
Son kullandığım konular (KULLANMA): {used_list}

Sadece JSON döndür (başka hiçbir şey yazma):
{{
  "title": "Video başlığı (max 90 karakter, merak uyandıran, emoji ile)",
  "hook": "İlk 3 saniye - izleyiciyi bağlayacak giriş cümlesi",
  "segments": [
    {{"time": "0-3s",  "text": "Hook cümlesi", "narration": "TTS metni", "visual": "görsel açıklaması"}},
    {{"time": "3-8s",  "text": "Konu girişi",   "narration": "TTS metni", "visual": "görsel açıklaması"}},
    {{"time": "8-20s", "text": "Ana içerik",    "narration": "TTS metni", "visual": "görsel açıklaması"}},
    {{"time": "20-30s","text": "Detay/gelişme", "narration": "TTS metni", "visual": "görsel açıklaması"}},
    {{"time": "30-45s","text": "Sonuç/etki",    "narration": "TTS metni", "visual": "görsel açıklaması"}},
    {{"time": "45-55s","text": "İlginç detay",  "narration": "TTS metni", "visual": "görsel açıklaması"}},
    {{"time": "55-60s","text": "İzleyiciye soru", "narration": "Konuyla ilgili merak uyandıran bir soru sor: Siz ne düşünüyorsunuz? Yorumlarda paylaşın!", "visual": "kamera yakın plan"}}
  ],
  "full_narration": "Tam anlatım metni (TTS için, 130-160 kelime). Son cümle mutlaka izleyiciye yönelik bir soru olmalı — örn: Siz bu konuda ne düşünüyorsunuz? Yorumlarda buluşalım!",
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
    import re as _re, json as _json
    if "```json" in text: text = text.split("```json")[1].split("```")[0]
    elif "```" in text:   text = text.split("```")[1].split("```")[0]
    text = text.strip()
    try:
        return _json.loads(text)
    except _json.JSONDecodeError:
        pass
    fixed = text.replace('\r\n', '\n').replace('\r', '\n')
    fixed = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', fixed)
    try:
        return _json.loads(fixed)
    except _json.JSONDecodeError:
        pass
    match = _re.search(r'\{[\s\S]*\}', fixed)
    if match:
        try:
            return _json.loads(match.group())
        except _json.JSONDecodeError:
            pass
    raise _json.JSONDecodeError("JSON parse basarisiz", text, 0)



def generate_with_claude(prompt):
    client = get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-5",
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

        import requests
        # Birkaç model dene
        models = [
            "gemini-2.0-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
        ]
        for model in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                body = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 3000, "temperature": 0.9}
                }
                r = requests.post(url, json=body, timeout=30, verify=False)
                if r.status_code == 429:
                    print(f"  ⚠ Gemini {model} rate limit, 20s bekliyor...")
                    import time; time.sleep(20)
                    r = requests.post(url, json=body, timeout=30, verify=False)
                if r.status_code == 200:
                    data = r.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    print(f"  ✅ Gemini {model} başarılı")
                    return text
                else:
                    print(f"  ⚠ Gemini {model} HTTP {r.status_code}")
            except Exception as me:
                print(f"  ⚠ Gemini {model} hata: {me}")
                continue
        raise Exception("Tüm Gemini modelleri başarısız")
    except Exception as e:
        raise Exception(f"Gemini hata: {e}")


def generate_with_groq(prompt):
    """Groq API ile içerik üretir (son çare)."""
    try:
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_key:
            try:
                from config import GROQ_API_KEY
                groq_key = GROQ_API_KEY
            except: pass
        if not groq_key:
            raise ValueError("GROQ_API_KEY bulunamadı")

        import requests
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 3000,
            "temperature": 0.9,
        }
        r = requests.post(url, json=body, headers=headers, timeout=30, verify=False)
        if r.status_code != 200:
            raise Exception(f"Groq HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise Exception(f"Groq hata: {e}")


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
        # 2. Gemini dene
        print("  → Gemini'ye geçiliyor...")
        try:
            text = generate_with_gemini(prompt)
            print("  ✅ Gemini başarılı")
        except Exception as e2:
            print(f"  ⚠ Gemini hata: {e2}")
            # 3. Groq dene
            print("  → Groq'a geçiliyor...")
            try:
                text = generate_with_groq(prompt)
                print("  ✅ Groq başarılı")
            except Exception as e3:
                raise Exception(f"Claude, Gemini ve Groq hepsi başarısız: {e} | {e2} | {e3}")

    content = parse_response(text)
    content["format"]       = format_type
    content["generated_at"] = datetime.now().isoformat()
    # Konuyu kaydet
    save_used_topic(content.get("topic", content.get("title", "bilinmiyor")))
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
