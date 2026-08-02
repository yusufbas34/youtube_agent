"""
Telegram Bot — YouTube Agent Komutları
"""

import os, json, threading, time, requests, urllib3, re
from datetime import datetime
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_bot_token():
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")

def get_chat_id():
    return os.environ.get("TELEGRAM_CHAT_ID", "")

def send(text: str, chat_id: str = None):
    token = get_bot_token()
    if not token: return
    cid = chat_id or get_chat_id()
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": cid, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=10, verify=False
        )
    except Exception as e:
        print(f"  ⚠ Telegram send hata: {e}")

_running = {}


# ── Tarih ────────────────────────────────────────────────────────

# Tarih konu önerileri bekleme
_pending_tarih_topics = {}


def _get_suggestions_prompt():
    import json as _j, os as _o
    used_list, yt_list = "yok", "yok"
    try:
        from history_content_generator import load_used_topics
        used = load_used_topics()
        used_list = ", ".join([t["topic"] for t in used[-30:]]) if used else "yok"
    except: pass
    try:
        hist_path = "data/tarih_history.json"
        if _o.path.exists(hist_path):
            with open(hist_path,"r",encoding="utf-8") as f:
                hist = _j.load(f)
            yt_list = ", ".join([h.get("title","") for h in hist[-30:] if h.get("title")]) or "yok"
    except: pass
    prompt = "YouTube Shorts icin 5 farkli, ilginc ve az bilinen Turkce tarih konusu oner.\n"
    prompt += "Her konu merak uyandiran, sasirtan olmali.\n\n"
    prompt += "Daha once yuklenenler (BUNLARI ONERME): " + yt_list + "\n"
    prompt += "Son kullanilanlar (BUNLARI ONERME): " + used_list + "\n\n"
    prompt += 'SADECE JSON dondur:\n[{"konu":"baslik","aciklama":"1 cumle"},...]'
    return prompt


def _call_ai_for_suggestions(prompt):
    import json as _j, os as _o, requests as _r
    # Claude
    try:
        import httpx, anthropic
        key = _o.environ.get("ANTHROPIC_API_KEY","")
        if not key:
            from config import ANTHROPIC_API_KEY; key = ANTHROPIC_API_KEY
        http = httpx.Client(verify=False)
        client = anthropic.Anthropic(api_key=key, http_client=http)
        msg = client.messages.create(model="claude-sonnet-4-5", max_tokens=800,
            messages=[{"role":"user","content":prompt}])
        text = msg.content[0].text.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        elif "```" in text: text = text.split("```")[1].split("```")[0]
        return _j.loads(text.strip())
    except Exception as e:
        print(f"Claude suggestions: {e}")
    # Gemini
    try:
        key = _o.environ.get("GEMINI_API_KEY","")
        if not key:
            from config import GEMINI_API_KEY; key = GEMINI_API_KEY
        for model in ["gemini-2.0-flash","gemini-1.5-flash-latest"]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            r = _r.post(url, json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"maxOutputTokens":800}},timeout=20,verify=False)
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if "```json" in text: text = text.split("```json")[1].split("```")[0]
                elif "```" in text: text = text.split("```")[1].split("```")[0]
                return _j.loads(text.strip())
    except Exception as e:
        print(f"Gemini suggestions: {e}")
    # Groq
    try:
        key = _o.environ.get("GROQ_API_KEY","")
        if not key:
            from config import GROQ_API_KEY; key = GROQ_API_KEY
        r = _r.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],"max_tokens":800},timeout=20,verify=False)
        if r.status_code == 200:
            text = r.json()["choices"][0]["message"]["content"].strip()
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text: text = text.split("```")[1].split("```")[0]
            return _j.loads(text.strip())
    except Exception as e:
        print(f"Groq suggestions: {e}")
    raise Exception("Tum AI servisleri basarisiz")


def _generate_tarih_suggestions(chat_id: str):
    send("Konu onerileri hazirlaniyor...", chat_id)
    try:
        prompt = _get_suggestions_prompt()
        suggestions = _call_ai_for_suggestions(prompt)
        if not suggestions or not isinstance(suggestions, list):
            raise Exception("Gecersiz format")
        _pending_tarih_topics[chat_id] = suggestions[:5]
        msg = "Tarih konusu sec (1-5):\n\n"
        for i, s in enumerate(suggestions[:5], 1):
            msg += f"{i}. {s.get('konu','?')}\n"
            msg += f"   {s.get('aciklama','')}\n\n"
        msg += "Numara yaz veya /tarih konu ile ozel konu gir"
        send(msg, chat_id)
    except Exception as e:
        send(f"Oneri hatasi: {str(e)[:150]}", chat_id)
        _pending_tarih_topics.pop(chat_id, None)



def cmd_tarih(chat_id: str, topic: str = None):
    if _running.get("tarih"):
        send("⏳ Tarih videosu zaten üretiliyor, bekle...", chat_id)
        return

    # Konu verilmişse direkt üret
    if topic:
        threading.Thread(target=_produce_tarih, args=(chat_id, topic), daemon=True).start()
        return

    # Konu önerileri sun
    threading.Thread(target=_generate_tarih_suggestions, args=(chat_id,), daemon=True).start()


def _produce_tarih(chat_id: str, topic: str = None):
    _running["tarih"] = True
    send(f"🎬 Tarih videosu üretimi başladı{(' — ' + topic) if topic else ''}...", chat_id)

    def run():
        try:
            from history_content_generator import generate_history_content, get_best_format
            from history_video_generator import create_history_video
            from uploader import run_upload
            from channel_config import TARIH_CHANNEL_ID, CHANNELS
            import json as _json

            send("🤖 İçerik üretiliyor...", chat_id)
            content = generate_history_content(topic=topic, format_type="timeline")
            send(f"📝 Konu: <b>{content['title'][:70]}</b>", chat_id)
            send("🎥 Türkçe video render ediliyor (~5-10 dk)...", chat_id)

            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = f"output/tarih/tarih_{ts}.mp4"
            Path("output/tarih").mkdir(parents=True, exist_ok=True)
            video_path = create_history_video(content, out, channel="tarih")

            send("📤 Tarih kanalına yükleniyor...", chat_id)
            meta = {}
            mp = video_path.replace(".mp4", ".json")
            if os.path.exists(mp):
                with open(mp, "r", encoding="utf-8") as f:
                    meta = _json.load(f)
            cp = {
                "title":       meta.get("title", content["title"])[:90],
                "description": meta.get("description", ""),
                "tags":        meta.get("tags", []),
                "hashtags":    meta.get("hashtags", []),
            }
            result = run_upload(cp, video_path, scheduled_time=None,
                               channel_id=TARIH_CHANNEL_ID, channel="tarih")
            _save_history("tarih", video_path, result, cp["title"])
            send(f"✅ <b>Tarih</b> yüklendi!\n🏛 {cp['title'][:80]}\n🔗 {result['url']}", chat_id)

            # Notes of History - aynı içerik İngilizce
            send("🇬🇧 Notes of History için İngilizce üretiliyor...", chat_id)
            try:
                from english_history_content_generator import generate_english_history_content
                en_content = generate_english_history_content(turkish_content=content)
                if not en_content:
                    send("⚠️ İngilizce çeviri başarısız", chat_id)
                else:
                    ts2 = datetime.now().strftime("%Y%m%d_%H%M%S") + "_en"
                    out2 = f"output/notesofhistory/notes_{ts2}.mp4"
                    Path("output/notesofhistory").mkdir(parents=True, exist_ok=True)
                    send(f"🎥 İngilizce video render ediliyor...", chat_id)
                    vpath2 = create_history_video(en_content, out2, channel="notesofhistory")
                    meta2 = {}
                    mp2 = vpath2.replace(".mp4", ".json")
                    if os.path.exists(mp2):
                        with open(mp2, "r", encoding="utf-8") as f:
                            meta2 = _json.load(f)
                    cp2 = {
                        "title":       meta2.get("title", en_content["title"])[:90],
                        "description": meta2.get("description", ""),
                        "tags":        meta2.get("tags", []),
                        "hashtags":    meta2.get("hashtags", []),
                    }
                    ch_id2 = CHANNELS.get("notesofhistory", {}).get("channel_id", "")
                    if os.path.exists("token_notesofhistory.json") and ch_id2:
                        send("📤 Notes of History kanalına yükleniyor...", chat_id)
                        result2 = run_upload(cp2, vpath2, scheduled_time=None,
                                            channel_id=ch_id2, channel="notesofhistory")
                        _save_history("notesofhistory", vpath2, result2, cp2["title"])
                        send(f"✅ <b>Notes of History</b> yüklendi!\n📖 {cp2['title'][:80]}\n🔗 {result2['url']}", chat_id)
                    else:
                        send("⚠️ Notes token/kanal ID eksik, yerel kaydedildi", chat_id)
            except Exception as ne:
                send(f"❌ Notes hatası: {str(ne)[:150]}", chat_id)

        except Exception as e:
            send(f"❌ Tarih hatası: {str(e)[:200]}", chat_id)
            print(f"  ⚠ telegram tarih hata: {e}")
            import traceback; traceback.print_exc()
        finally:
            _running["tarih"] = False

    threading.Thread(target=run, daemon=True).start()


# ── Yardımcılar ───────────────────────────────────────────────────

def _save_history(channel: str, video_path: str, result: dict, title: str):
    """Yüklenen videoyu history dosyasına kaydet."""
    try:
        hist_path = f"data/{channel}_history.json"
        os.makedirs("data", exist_ok=True)
        hist = []
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                hist = json.load(f)
        hist.append({
            "video_path":  video_path,
            "video_id":    result.get("video_id", ""),
            "url":         result.get("url", ""),
            "title":       title,
            "uploaded_at": datetime.now().isoformat(),
            "source":      "telegram",
        })
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ History kayıt hata ({channel}): {e}")


def cmd_durum(chat_id: str):
    lines = ["📊 <b>Kanal Durumları</b>\n"]
    for ch, emoji in [("tarih","🏛")]:
        durum = "🔄 Çalışıyor" if _running.get(ch) else "✅ Boşta"
        lines.append(f"{emoji} <b>{ch.capitalize()}</b>: {durum}")
    try:
        for ch in ["tarih"]:
            p = f"data/{ch}_queue.json"
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    q = json.load(f)
                pending = len([x for x in q if x.get("status") == "bekliyor"])
                if pending:
                    lines.append(f"   ↳ {pending} bekliyor")
    except: pass
    lines.append(f"\n🕐 {datetime.now().strftime('%H:%M:%S')}")
    send("\n".join(lines), chat_id)


def cmd_iptal(chat_id: str):
    stopped = [ch for ch in list(_running.keys()) if _running.get(ch)]
    for ch in stopped:
        _running[ch] = False
    send(f"🛑 Durduruldu: {', '.join(stopped)}" if stopped else "ℹ️ Çalışan işlem yok.", chat_id)


def cmd_yardim(chat_id: str):
    send(
        "🤖 <b>YouTube Agent Bot</b>\n\n"
        "/tarih — Tarih videosu üret + yükle\n"
        "/tarih &lt;konu&gt; — Belirli konuda tarih videosu\n"
        "/durum — Kanal durumları\n"
        "/iptal — Çalışan işlemi durdur\n"
        "/yardim — Bu mesaj",
        chat_id
    )


# ── Polling ───────────────────────────────────────────────────────

def handle_update(update: dict):
    msg = update.get("message") or update.get("edited_message")
    if not msg: return
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text    = (msg.get("text") or "").strip()

    allowed = get_chat_id()
    if allowed and chat_id != allowed:
        send("⛔ Yetkisiz erişim.", chat_id)
        return

    # Numara seçimi
    if text.strip().isdigit():
        idx = int(text.strip()) - 1
        # Tarih konu seçimi
        if chat_id in _pending_tarih_topics:
            topics = _pending_tarih_topics.get(chat_id, [])
            if 0 <= idx < len(topics):
                topic = topics[idx]["konu"]
                del _pending_tarih_topics[chat_id]
                _produce_tarih(chat_id, topic=topic)
            else:
                send(f"❌ Geçersiz numara. 1-{len(topics)} arası yaz.", chat_id)
            return

    if not text.startswith("/"): return

    parts   = text.split(None, 1)
    command = parts[0].lower().split("@")[0]
    args    = parts[1].strip() if len(parts) > 1 else ""

    print(f"  📨 Telegram komut: {command} {args}")

    if command == "/tarih":
        if args:
            _produce_tarih(chat_id, topic=args)
        else:
            cmd_tarih(chat_id)
    elif command == "/durum":
        cmd_durum(chat_id)
    elif command == "/iptal":
        cmd_iptal(chat_id)
    elif command in ("/yardim", "/start", "/help"):
        cmd_yardim(chat_id)
    else:
        send(f"❓ Bilinmeyen komut: {command}\n/yardim yazarak komutları görebilirsin.", chat_id)


def start_polling():
    token = get_bot_token()
    if not token:
        print("  ⚠ TELEGRAM_BOT_TOKEN yok, bot başlatılmadı")
        return
    print("  🤖 Telegram bot başlatıldı")
    send("🤖 YouTube Agent Bot başladı!\n/yardim — komutları görmek için")
    offset = 0
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                timeout=35, verify=False
            )
            if r.status_code == 200:
                for update in r.json().get("result", []):
                    offset = update["update_id"] + 1
                    try: handle_update(update)
                    except Exception as e: print(f"  ⚠ Update hatası: {e}")
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            print(f"  ⚠ Polling hata: {e}")
            time.sleep(5)


def start_bot_thread():
    t = threading.Thread(target=start_polling, daemon=True, name="TelegramBot")
    t.start()
    return t


if __name__ == "__main__":
    start_polling()
