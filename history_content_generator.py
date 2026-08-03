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


def build_prompt(topic, format_type, today, source_extract: str = None, source_title: str = None):
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

    if source_extract:
        source_block = f"""
KAYNAK (Wikipedia — "{source_title}"):
\"\"\"
{source_extract[:3000]}
\"\"\"

KRİTİK — DOĞRULUK KURALI:
- Senaryodaki TÜM tarih, isim, sayı, olay ve iddialar SADECE yukarıdaki kaynaktan gelmeli.
- Kaynakta olmayan hiçbir spesifik detayı (tarih, rakam, isim) UYDURMA.
- Kaynakta net olmayan bir nokta varsa, spesifik uydurma detay yerine genel/muğlak bir ifade kullan.
- Kaynağı YouTube Shorts diline çevir ama içeriğini değiştirme, abartma veya yanlış aktarma.
"""
    else:
        source_block = """
KRİTİK — DOĞRULUK KURALI:
- Bu konu için doğrulanmış bir kaynak bulunamadı.
- SADECE yaygın olarak bilinen, tartışmasız, ansiklopedik düzeyde kesin tarihi olgulara dayan.
- Emin olmadığın, nadir/tartışmalı/spesifik detayları (kesin tarih, rakam, alıntı) UYDURMA — genel ifade kullan.
"""

    return f"""
Sen YouTube Shorts için Türkçe tarih videoları üreten bir içerik üreticisisin.

{topic_prompt}

Video formatı: {fmt_desc}
{source_block}
KRİTİK KURALLAR:
1. FARKLI ve AZ BİLİNEN bir konu seç — izleyiciyi şaşırtacak, "bunu bilmiyordum" dedirtecek
2. Başlık merak uyandırmalı, soru formatında veya şaşırtıcı bir iddia içermeli
3. Her segment kısa, vurucu, sinematik olmalı — belgesel anlatıcı tonu
4. narration alanı TTS için doğal konuşma dili olmalı — kısa ve etkili cümleler
5. full_narration TOPLAM 130-160 kelime olmalı (60 saniye video için kritik!)
6. Türkçe karakterleri doğru kullan: ğ, ü, ş, ı, ö, ç
7. Her segment için "visual" alanını İNGİLİZCE yaz — stok görsel/video arama sorgusu olarak kullanılacak (ör: "ottoman soldiers marching, dramatic lighting")

Daha önce yüklediklerim (KULLANMA): {yt_list}
Son kullandığım konular (KULLANMA): {used_list}

Sadece JSON döndür (başka hiçbir şey yazma):
{{
  "title": "Video başlığı (max 90 karakter, merak uyandıran, emoji ile)",
  "hook": "İlk 3 saniye - izleyiciyi bağlayacak giriş cümlesi",
  "segments": [
    {{"time": "0-3s",  "text": "Hook cümlesi", "narration": "TTS metni", "visual": "English visual search query"}},
    {{"time": "3-8s",  "text": "Konu girişi",   "narration": "TTS metni", "visual": "English visual search query"}},
    {{"time": "8-20s", "text": "Ana içerik",    "narration": "TTS metni", "visual": "English visual search query"}},
    {{"time": "20-30s","text": "Detay/gelişme", "narration": "TTS metni", "visual": "English visual search query"}},
    {{"time": "30-45s","text": "Sonuç/etki",    "narration": "TTS metni", "visual": "English visual search query"}},
    {{"time": "45-55s","text": "İlginç detay",  "narration": "TTS metni", "visual": "English visual search query"}},
    {{"time": "55-60s","text": "İzleyiciye soru", "narration": "Konuyla ilgili merak uyandıran bir soru sor: Siz ne düşünüyorsunuz? Yorumlarda paylaşın!", "visual": "close up camera, dramatic"}}
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


def wiki_search_topic(query: str, lang: str = "tr") -> dict | None:
    """
    Wikipedia'da konuyu arar, en iyi eşleşen maddenin özetini döner.
    Bulamazsa None döner (konu doğrulanamadı demektir).
    """
    import requests
    try:
        s = requests.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query,
                    "format": "json", "srlimit": 1},
            timeout=10, verify=False,
            headers={"User-Agent": "TarihKanaliBot/1.0"}
        )
        hits = s.json().get("query", {}).get("search", [])
        if not hits:
            return None
        title = hits[0]["title"]

        r = requests.get(
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}",
            timeout=10, verify=False,
            headers={"User-Agent": "TarihKanaliBot/1.0"}
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("type") == "disambiguation":
            return None
        extract = data.get("extract", "")
        if not extract or len(extract) < 80:
            return None
        return {
            "title":   data.get("title", title),
            "extract": extract,
            "url":     data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        }
    except Exception as e:
        print(f"  ⚠ Wikipedia arama hatası ({lang}): {e}")
        return None


def _suggest_topic_name(used_list: str, yt_list: str, attempt: int = 0) -> str | None:
    """AI'dan tek bir tarih konusu adı ister (script değil, sadece başlık)."""
    variety_hint = (
        "" if attempt == 0 else
        " (Önceki deneme Wikipedia'da doğrulanamadı — FARKLI ve Wikipedia'da kesinlikle "
        "maddesi olan, daha bilinen bir konu seç.)"
    )
    prompt = f"""YouTube Shorts için ilginç, az bilinen ama GERÇEK bir Türkçe tarih konusu öner.{variety_hint}
Konu Wikipedia'da kesinlikle bir maddesi olan, doğrulanabilir bir olay/kişi/dönem olmalı — uydurma olmasın.

Daha önce kullanılanlar (SEÇME): {used_list}
Daha önce yüklenenler (SEÇME): {yt_list}

SADECE konu adını tek satırda yaz, başka hiçbir şey yazma. Örnek çıktı: Bizans-Sasani Savaşları"""

    for fn in (generate_with_claude, generate_with_gemini, generate_with_groq):
        try:
            text = fn(prompt).strip().strip('"').strip()
            text = text.split("\n")[0].strip()
            if 3 < len(text) < 100:
                return text
        except Exception as e:
            print(f"  ⚠ Konu önerisi hatası: {e}")
    return None


def pick_verified_topic(hint: str = None, max_attempts: int = 4) -> dict | None:
    """
    Konu belirler ve Wikipedia'da doğrular.
    hint verilmişse önce onu dener, doğrulanamazsa AI'dan yeni öneriler ister.
    Döner: {"topic": ..., "wiki": {"title","extract","url"}} veya None (doğrulanamadı).
    """
    used = load_used_topics()
    used_list = ", ".join([t["topic"] for t in used[-50:]]) if used else "yok"
    yt_list = ", ".join(load_youtube_uploaded_topics()[-30:]) or "yok"

    for attempt in range(max_attempts):
        candidate = hint if (hint and attempt == 0) else _suggest_topic_name(used_list, yt_list, attempt)
        if not candidate:
            continue
        wiki = wiki_search_topic(candidate, lang="tr")
        if not wiki:
            wiki = wiki_search_topic(candidate, lang="en")
        if wiki:
            print(f"  ✅ Kaynak doğrulandı: {wiki['title']} ({wiki['url']})")
            return {"topic": candidate, "wiki": wiki}
        print(f"  ⚠ Doğrulanamadı ({attempt+1}/{max_attempts}): {candidate}")
    return None


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
    today = datetime.now().strftime("%d %B")

    # Konuyu Wikipedia ile doğrula — script yazılmadan ÖNCE
    print("  → Konu doğrulanıyor (Wikipedia)...")
    verified = pick_verified_topic(hint=topic)
    if verified:
        topic_final    = verified["topic"]
        source_extract = verified["wiki"]["extract"]
        source_title   = verified["wiki"]["title"]
        source_url     = verified["wiki"]["url"]
    else:
        print("  ⚠ Kaynak doğrulanamadı, genel bilgi kısıtıyla devam ediliyor")
        topic_final    = topic
        source_extract = None
        source_title   = None
        source_url     = None

    prompt = build_prompt(topic_final, format_type, today, source_extract, source_title)

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
    content["verified"]     = bool(source_url)
    content["source_url"]   = source_url
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
