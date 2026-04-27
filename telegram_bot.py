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
_pending_selection = {}  # {chat_id: [quote1, quote2, ...]}


# ── Tarih ────────────────────────────────────────────────────────

# Tarih konu önerileri bekleme
_pending_tarih_topics = {}


def _generate_tarih_suggestions(chat_id: str):
    """5 farklı tarih konusu önerisi üretir."""
    send("🤔 5 konu önerisi hazırlanıyor...", chat_id)
    try:
        import httpx, anthropic, json as _json, os as _os
        from config import ANTHROPIC_API_KEY
        from history_content_generator import load_used_topics, load_youtube_uploaded_topics

        used = load_used_topics()
        yt = load_youtube_uploaded_topics()
        used_list = ", ".join([t["topic"] for t in used[-30:]]) if used else "yok"
        yt_list = ", ".join(yt[-20:]) if yt else "yok"

        http = httpx.Client(verify=False)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=800,
            messages=[{"role":"user","content":f"""YouTube Shorts için 5 farklı, ilginç ve az bilinen Türkçe tarih konusu öner.
Her konu bir Shorts videosu için uygun olmalı — merak uyandıran, şaşırtıcı.

Daha önce yüklediklerim (KULLANMA): {yt_list}
Son kullanılanlar (KULLANMA): {used_list}

Sadece JSON döndür:
[
  {{"konu": "konu başlığı", "aciklama": "neden ilginç, 1 cümle"}},
  ...
]"""}]
        )
        text = msg.content[0].text.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        elif "```" in text: text = text.split("```")[1].split("```")[0]
        suggestions = _json.loads(text.strip())

        _pending_tarih_topics[chat_id] = suggestions
        lines = ["📋 <b>Konu seç (1-5):</b>\n"]
        for i, s in enumerate(suggestions[:5], 1):
            lines.append(f"{i}. 🏛 <b>{s['konu']}</b>\n   <i>{s['aciklama']}</i>")
        lines.append("\n<i>Numara yaz veya /tarih konu başlığı ile özel konu gir</i>")
        send("\n\n".join(lines) if len(lines) > 2 else "\n".join(lines), chat_id)
    except Exception as e:
        send(f"❌ Öneri üretilemedi: {str(e)[:100]}\n/tarih konuadı ile devam edebilirsin.", chat_id)
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


# ── Sözler ───────────────────────────────────────────────────────

def cmd_sozler(chat_id: str, custom_text: str = None):
    """
    /sozler "söz metni" → direkt o sözü yap
    /sozler             → listeden 10 seçenek sun
    """
    if _running.get("sozler"):
        send("⏳ Söz videosu zaten üretiliyor, bekle...", chat_id)
        return

    # Özel söz verilmişse direkt üret
    if custom_text:
        quote = {
            "id":       f"tg_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "text":     custom_text,
            "author":   "Anonim",
            "category": "motivasyon",
            "used":     False,
        }
        _produce_sozler(chat_id, quote)
        return

    # Liste sun
    try:
        from quotes_manager import load_quotes
        quotes = [q for q in load_quotes() if not q.get("used")][:10]
        if not quotes:
            send("❌ Kullanılabilir söz bulunamadı!", chat_id)
            return

        _pending_selection[chat_id] = quotes
        lines = ["📋 <b>Söz seç (1-10):</b>\n"]
        for i, q in enumerate(quotes, 1):
            text   = q.get("text", "")[:60]
            author = q.get("author", "")
            suffix = f" <i>— {author}</i>" if author and author != "Anonim" else ""
            lines.append(f"{i}. {text}...{suffix}")
        lines.append("\n<i>Numara yaz seç, veya /sozler \"kendi sözün\" ile özel söz gir</i>")
        send("\n".join(lines), chat_id)
    except Exception as e:
        send(f"❌ Hata: {str(e)[:200]}", chat_id)


def _produce_sozler(chat_id: str, quote: dict):
    """Sözü video yapıp yükle, history'e kaydet."""
    _running["sozler"] = True
    send(f"🎬 Video üretiliyor...\n📝 <i>{quote.get('text','')[:80]}</i>", chat_id)

    def run():
        try:
            from quote_video_generator import create_quote_video
            from uploader import run_upload
            from channel_config import SOZLER_CHANNEL_ID

            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = f"output/sozler/quote_{ts}.mp4"
            Path("output/sozler").mkdir(parents=True, exist_ok=True)
            video_path = create_quote_video(quote, out)

            send("📤 YouTube'a yükleniyor...", chat_id)
            title = (quote.get("text","")[:85] + " — " + quote.get("author","Anonim"))
            cp = {
                "title":       title[:90],
                "description": quote.get("text","") + "\n\n— " + quote.get("author","Anonim") + "\n\n#motivasyon #shorts",
                "tags":        ["motivasyon","ozlusoz","shorts","keşfet","viral"],
                "hashtags":    ["#motivasyon","#ozlusoz","#shorts","#keşfet"],
            }
            result = run_upload(cp, video_path, scheduled_time=None,
                               channel_id=SOZLER_CHANNEL_ID, channel="sozler")

            # Kullanıldı işaretle
            try:
                if quote.get("id") and not str(quote["id"]).startswith("tg_"):
                    from quotes_manager import mark_quote_used
                    mark_quote_used(quote["id"], result["url"])
            except Exception as me:
                print(f"  ⚠ mark_quote_used hata: {me}")

            # History kaydet
            _save_history("sozler", video_path, result, cp["title"])

            send(f"✅ <b>Sözler</b> yüklendi!\n📝 {quote.get('text','')[:80]}\n🔗 {result['url']}", chat_id)
        except Exception as e:
            send(f"❌ Sözler hatası: {str(e)[:200]}", chat_id)
            print(f"  ⚠ telegram _produce_sozler hata: {e}")
        finally:
            _running["sozler"] = False

    threading.Thread(target=run, daemon=True).start()


# ── Viral ─────────────────────────────────────────────────────────

# Viral seçim bekleme: {chat_id: [item1, item2, ...]}
_pending_viral = {}


def cmd_viral(chat_id: str):
    if _running.get("viral"):
        send("⏳ Viral işlem zaten çalışıyor, bekle...", chat_id)
        return

    send("🔍 İçerik kontrol ediliyor...", chat_id)

    def fetch():
        try:
            from viral_scraper import check_new_tweets, add_to_viral_queue, load_queue

            new_tweets = check_new_tweets(force=True)
            if new_tweets:
                add_to_viral_queue(new_tweets)

            queue   = load_queue()
            pending = [q for q in queue if q.get("status") == "bekliyor"][:10]

            if not pending:
                send("📭 Bekleyen içerik yok.", chat_id)
                return

            _pending_viral[chat_id] = pending
            lines = [f"📋 <b>Viral içerik seç (1-{len(pending)}):</b>\n"]
            for i, item in enumerate(pending, 1):
                text   = item.get("text","")[:70]
                source = item.get("source","")
                has_v  = "🎥" if item.get("has_video") else "📝"
                lines.append(f"{i}. {has_v} {text}...")
            lines.append("\n<i>Numara yaz → video üret + yükle</i>")
            send("\n".join(lines), chat_id)
        except Exception as e:
            send(f"❌ Hata: {str(e)[:200]}", chat_id)

    threading.Thread(target=fetch, daemon=True).start()


def _produce_viral(chat_id: str, item: dict):
    """Seçilen viral içeriği video yapıp yükle."""
    _running["viral"] = True
    send(f"🎬 Video üretiliyor...\n📱 <i>{item.get('text','')[:80]}</i>", chat_id)

    def run():
        try:
            from viral_video_generator import create_viral_video
            from uploader import run_upload
            from channel_config import VIRAL_CHANNEL_ID

            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = f"output/viral/viral_{ts}.mp4"
            Path("output/viral").mkdir(parents=True, exist_ok=True)
            vpath = create_viral_video(item, out)

            if not vpath:
                send("❌ Video indirilemedi.", chat_id)
                return

            send("📤 YouTube'a yükleniyor...", chat_id)
            meta = {}
            mp = vpath.replace(".mp4", ".json")
            if os.path.exists(mp):
                with open(mp, "r", encoding="utf-8") as f:
                    meta = json.load(f)

            raw_title   = meta.get("title", item["text"][:90])
            clean_title = re.sub(r'\s*\bVideo\b\s*$', '', raw_title, flags=re.IGNORECASE).strip()
            cp = {
                "title":       clean_title[:90],
                "description": meta.get("description", "#viral #shorts"),
                "tags":        meta.get("tags", ["viral","shorts"]),
                "hashtags":    meta.get("hashtags", ["#viral","#shorts"]),
            }
            result = run_upload(cp, vpath, scheduled_time=None,
                               channel_id=VIRAL_CHANNEL_ID, channel="viral")

            # Queue'dan sil
            try:
                from viral_scraper import load_queue, save_queue
                q = load_queue()
                for qi in q:
                    if qi.get("id") == item.get("id"):
                        qi["status"] = "yuklendi"
                        qi["video_url"] = result["url"]
                save_queue(q)
            except: pass

            _save_history("viral", vpath, result, cp["title"])
            send(f"✅ <b>Viral</b> yüklendi!\n📱 {clean_title[:80]}\n🔗 {result['url']}", chat_id)
        except Exception as e:
            send(f"❌ Viral hatası: {str(e)[:200]}", chat_id)
            print(f"  ⚠ telegram _produce_viral hata: {e}")
        finally:
            _running["viral"] = False

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
    for ch, emoji in [("tarih","🏛"), ("sozler","📝"), ("viral","📱")]:
        durum = "🔄 Çalışıyor" if _running.get(ch) else "✅ Boşta"
        lines.append(f"{emoji} <b>{ch.capitalize()}</b>: {durum}")
    try:
        for ch in ["sozler", "tarih", "viral"]:
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
        '/sozler — 10 söz listesi sun, numara seç\n'
        '/sozler "söz metni" — Özel söz ile video yap\n'
        "/viral — Tweet kontrol et + video yap + yükle\n"
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
        # Söz seçimi
        if chat_id in _pending_selection:
            quotes = _pending_selection.get(chat_id, [])
            if 0 <= idx < len(quotes):
                del _pending_selection[chat_id]
                _produce_sozler(chat_id, quotes[idx])
            else:
                send(f"❌ Geçersiz numara. 1-{len(quotes)} arası yaz.", chat_id)
            return
        # Viral seçimi
        if chat_id in _pending_viral:
            items = _pending_viral.get(chat_id, [])
            if 0 <= idx < len(items):
                del _pending_viral[chat_id]
                _produce_viral(chat_id, items[idx])
            else:
                send(f"❌ Geçersiz numara. 1-{len(items)} arası yaz.", chat_id)
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
    elif command == "/sozler":
        match  = re.search(r'["\'](.*?)["\']', args, re.DOTALL)
        custom = match.group(1).strip() if match else None
        cmd_sozler(chat_id, custom_text=custom)
    elif command == "/viral":
        cmd_viral(chat_id)
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
