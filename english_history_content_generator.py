"""
İngilizce Tarih Kanalı İçerik Üreticisi — Notes of History
Türkçe içeriği İngilizce'ye çevirir ve İngilizce video üretir.
"""

import json, os, re
from datetime import datetime


def get_client():
    import httpx
    from config import ANTHROPIC_API_KEY
    import anthropic
    http = httpx.Client(verify=False)
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)


def _build_translate_prompt(turkish_content: dict) -> str:
    return f"""Translate this Turkish YouTube Shorts history video content to English.
Keep the same structure, dramatic style, and engaging tone.
The channel is "Notes of History" - make it sound professional and captivating.

Turkish content:
{json.dumps(turkish_content, ensure_ascii=False, indent=2)}

Return ONLY a JSON object with the same structure but all text fields translated to English.
Keep all non-text fields (colors, format, etc.) unchanged.
Make the title catchy and SEO-friendly for English YouTube.
For segments, translate both "text" and "narration" fields.
For tags/hashtags, use English equivalents."""


def _parse_translation(text: str) -> dict:
    if "```json" in text: text = text.split("```json")[1].split("```")[0]
    elif "```" in text:   text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def translate_content_to_english(turkish_content: dict) -> dict:
    """Türkçe içeriği İngilizce'ye çevirir. Claude → Gemini → Groq."""
    prompt = _build_translate_prompt(turkish_content)

    # 1. Claude
    try:
        client = get_client()
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        result = _parse_translation(msg.content[0].text.strip())
        print("  ✅ Claude çeviri tamamlandı")
        return result
    except Exception as e:
        print(f"  ⚠ Claude çeviri hatası: {e}")

    # 2. Gemini
    try:
        import requests, os
        key = os.environ.get("GEMINI_API_KEY","")
        if not key:
            try:
                from config import GEMINI_API_KEY; key=GEMINI_API_KEY
            except: pass
        if key:
            for model in ["gemini-2.0-flash","gemini-1.5-flash-latest"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                    r = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}],
                        "generationConfig":{"maxOutputTokens":3000,"temperature":0.3}},
                        timeout=30, verify=False)
                    if r.status_code==200:
                        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                        result = _parse_translation(text)
                        print(f"  ✅ Gemini ({model}) çeviri tamamlandı")
                        return result
                except Exception as me:
                    print(f"  ⚠ Gemini {model}: {me}")
    except Exception as e:
        print(f"  ⚠ Gemini çeviri hatası: {e}")

    # 3. Groq
    try:
        import requests, os
        key = os.environ.get("GROQ_API_KEY","")
        if not key:
            try:
                from config import GROQ_API_KEY; key=GROQ_API_KEY
            except: pass
        if key:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
                json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],
                      "max_tokens":3000,"temperature":0.3}, timeout=30, verify=False)
            if r.status_code==200:
                text = r.json()["choices"][0]["message"]["content"].strip()
                result = _parse_translation(text)
                print("  ✅ Groq çeviri tamamlandı")
                return result
    except Exception as e:
        print(f"  ⚠ Groq çeviri hatası: {e}")

    print("  ❌ Tüm çeviri servisleri başarısız")
    return None


def generate_english_history_content(topic: str = None, format_type: str = "timeline",
                                      turkish_content: dict = None) -> dict:
    """
    İngilizce tarih içeriği üretir.
    turkish_content verilirse MUTLAKA onu çevirir, asla yeni içerik üretmez.
    """
    if turkish_content:
        # Türkçe içeriği çevir — 3 deneme
        for attempt in range(3):
            english = translate_content_to_english(turkish_content)
            if english:
                english["channel"] = "notesofhistory"
                english["generated_at"] = datetime.now().isoformat()
                english["tags"] = list(set(
                    english.get("tags", []) +
                    ["history","shorts","historical","facts","historyfacts","notesofhistory"]
                ))[:30]
                english["hashtags"] = list(set(
                    english.get("hashtags", []) +
                    ["#history","#shorts","#historyfacts","#notesofhistory","#historical"]
                ))[:15]
                return english
            print(f"  ⚠ Çeviri denemesi {attempt+1} başarısız, tekrar deneniyor...")
        raise Exception("Türkçe→İngilizce çeviri 3 denemede başarısız oldu")

    # Direkt İngilizce üret
    today = datetime.now().strftime("%B %d")

    # Kullanılan konuları yükle
    used = _load_used_topics_en()
    used_list = ", ".join([t["topic"] for t in used[-30:]]) if used else "none"

    topic_prompt = f'Topic: "{topic}"' if topic else f"An interesting historical event or fact (today is {today}). Avoid overused topics like Titanic. Pick lesser-known but fascinating history."

    format_desc = {
        "timeline": "Chronological events (beginning → development → conclusion)",
        "illustrated": "Deep dive into a single event or person",
        "simple": "Short, striking historical fact",
    }.get(format_type, "Chronological events")

    prompt = f"""You are creating content for a YouTube Shorts history channel called "Notes of History".

{topic_prompt}
Format: {format_desc}
Previously used topics (DO NOT USE THESE): {used_list}

Return ONLY JSON:
{{
  "title": "Catchy YouTube title (max 90 chars, with emoji, SEO-friendly)",
  "hook": "First 3 seconds hook sentence",
  "segments": [
    {{"time": "0-3s",  "text": "Hook", "narration": "TTS text", "visual": "visual description"}},
    {{"time": "3-8s",  "text": "Intro", "narration": "TTS text", "visual": "visual description"}},
    {{"time": "8-20s", "text": "Main content", "narration": "TTS text", "visual": "visual description"}},
    {{"time": "20-30s","text": "Details", "narration": "TTS text", "visual": "visual description"}},
    {{"time": "30-45s","text": "Result/impact", "narration": "TTS text", "visual": "visual description"}},
    {{"time": "45-55s","text": "Interesting fact", "narration": "TTS text", "visual": "visual description"}},
    {{"time": "55-60s","text": "Question for viewers", "narration": "Ask a thought-provoking question related to the topic: What do you think? Let me know in the comments!", "visual": "close up camera"}}
  ],
  "full_narration": "Full narration text for TTS (130-160 words). The last sentence MUST be a question directed at viewers — e.g.: What do you think about this? Let me know in the comments below!",
  "description": "YouTube description (200-300 chars)",
  "tags": ["history","shorts","historyfacts","notesofhistory"],
  "hashtags": ["#history","#shorts","#historyfacts","#notesofhistory"],
  "topic": "topic name",
  "period": "time period (e.g. Ancient Rome, Ottoman Empire, Modern)",
  "format": "{format_type}",
  "background_color": "#1a0a05",
  "accent_color": "#d97706",
  "pexels_queries": [
    "dramatic historical visual query 1",
    "period-specific atmospheric query 2",
    "cinematic backup query 3"
  ]
}}"""

    # Claude → Gemini → Groq fallback
    text = None
    for name, fn in [("Claude", _claude), ("Gemini", _gemini), ("Groq", _groq)]:
        try:
            print(f"  → {name} ile İngilizce içerik üretiliyor...")
            text = fn(prompt)
            print(f"  ✅ {name} başarılı")
            break
        except Exception as e:
            print(f"  ⚠ {name}: {e}")

    if not text:
        raise Exception("Tüm AI servisleri başarısız")

    content = _parse(text)
    content["format"] = format_type
    content["channel"] = "notesofhistory"
    content["generated_at"] = datetime.now().isoformat()
    _save_used_topic_en(content.get("topic", content.get("title", "unknown")))
    return content


def _parse(text):
    if "```json" in text: text = text.split("```json")[1].split("```")[0]
    elif "```" in text:   text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def _claude(prompt):
    client = get_client()
    msg = client.messages.create(
        model="claude-sonnet-4-5", max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()


def _gemini(prompt):
    import requests, time
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        try:
            from config import GEMINI_API_KEY; key = GEMINI_API_KEY
        except: pass
    if not key: raise ValueError("No GEMINI_API_KEY")
    for model in ["gemini-2.0-flash", "gemini-1.5-flash-latest"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            r = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}],
                "generationConfig":{"maxOutputTokens":3000,"temperature":0.9}}, timeout=30, verify=False)
            if r.status_code == 429:
                time.sleep(20)
                r = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}],
                    "generationConfig":{"maxOutputTokens":3000,"temperature":0.9}}, timeout=30, verify=False)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except: continue
    raise Exception("Gemini failed")


def _groq(prompt):
    import requests
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        try:
            from config import GROQ_API_KEY; key = GROQ_API_KEY
        except: pass
    if not key: raise ValueError("No GROQ_API_KEY")
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],
              "max_tokens":3000,"temperature":0.9}, timeout=30, verify=False)
    if r.status_code != 200: raise Exception(f"Groq {r.status_code}")
    return r.json()["choices"][0]["message"]["content"].strip()


def _load_used_topics_en() -> list:
    try:
        path = "data/notesofhistory_used_topics.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return []


def _save_used_topic_en(topic: str):
    try:
        path = "data/notesofhistory_used_topics.json"
        os.makedirs("data", exist_ok=True)
        topics = _load_used_topics_en()
        topics.append({"topic": topic, "date": datetime.now().isoformat()})
        topics = topics[-100:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
    except: pass


if __name__ == "__main__":
    print("Test: English history content...")
    content = generate_english_history_content(format_type="timeline")
    print(f"Title: {content['title']}")
    print(f"Hook: {content['hook']}")
