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

def cmd_tarih(chat_id: str, topic: str = None):
    if _running.get("tarih"):
        send("⏳ Tarih videosu zaten üretiliyor, bekle...", chat_id)
        return
    _running["tarih"] = True
    send(f"🎬 Tarih videosu üretimi başladı{' — ' + topic if topic else ''}...", chat_id)

    def run():
        try:
            from history_content_generator import generate_history_content, get_best_format
            from history_video_generator import create_history_video
            from uploader import run_upload
            from channel_config import TARIH_CHANNEL_ID
            import json as _json

            send("🤖 İçerik üretiliyor...", chat_id)
            content = generate_history_content(topic=topic, format_type="timeline")
            send(f"📝 Konu: <b>{content['title'][:70]}</b>", chat_id)
            send("🎥 Video render ediliyor (~5-10 dk)...", chat_id)

            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = f"output/tarih/tarih_{ts}.mp4"
            Path("output/tarih").mkdir(parents=True, exist_ok=True)
            video_path = create_history_video(content, out)

            send("📤 YouTube'a yükleniyor...", chat_id)
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
            # History kaydet
            _save_history("tarih", video_path, result, cp["title"])
            send(f"✅ <b>Tarih</b> yüklendi!\n🏛 {cp['title'][:80]}\n🔗 {result['url']}", chat_id)
        except Exception as e:
            send(f"❌ Tarih hatası: {str(e)[:200]}", chat_id)
            print(f"  ⚠ telegram cmd_tarih hata: {e}")
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

def cmd_viral(chat_id: str):
    if _running.get("viral"):
        send("⏳ Viral işlem zaten çalışıyor, bekle...", chat_id)
        return
    _running["viral"] = True
    send("🔍 Tweet'ler kontrol ediliyor...", chat_id)

    def run():
        try:
            from viral_scraper import check_new_tweets, add_to_viral_queue, load_queue
            from viral_video_generator import create_viral_video
            from uploader import run_upload
            from channel_config import VIRAL_CHANNEL_ID

            new_tweets = check_new_tweets(force=True)
            queue = load_queue()

            if not new_tweets and not queue:
                send("📭 Yeni tweet veya bekleyen video yok.", chat_id)
                return

            if new_tweets:
                added = add_to_viral_queue(new_tweets)
                send(f"📥 {len(new_tweets)} yeni tweet, {added} kuyruğa eklendi.", chat_id)
                queue = load_queue()

            pending = [q for q in queue if q.get("status") == "bekliyor"]
            if not pending:
                send("📭 Bekleyen tweet yok.", chat_id)
                return

            item = pending[0]
            send(f"🎬 Video üretiliyor:\n<i>{item['text'][:80]}</i>", chat_id)

            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = f"output/viral/viral_{ts}.mp4"
            Path("output/viral").mkdir(parents=True, exist_ok=True)
            vpath = create_viral_video(item, out)

            if not vpath:
                send("❌ Video indirilemedi (tweet'te video olmayabilir).", chat_id)
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
            _save_history("viral", vpath, result, cp["title"])
            send(f"✅ <b>Viral</b> yüklendi!\n📱 {clean_title[:80]}\n🔗 {result['url']}", chat_id)
        except Exception as e:
            send(f"❌ Viral hatası: {str(e)[:200]}", chat_id)
            print(f"  ⚠ telegram cmd_viral hata: {e}")
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

    # Numara seçimi (bekleyen liste varsa)
    if chat_id in _pending_selection and text.strip().isdigit():
        idx    = int(text.strip()) - 1
        quotes = _pending_selection.get(chat_id, [])
        if 0 <= idx < len(quotes):
            del _pending_selection[chat_id]
            _produce_sozler(chat_id, quotes[idx])
        else:
            send(f"❌ Geçersiz numara. 1-{len(quotes)} arası yaz.", chat_id)
        return

    if not text.startswith("/"): return

    parts   = text.split(None, 1)
    command = parts[0].lower().split("@")[0]
    args    = parts[1].strip() if len(parts) > 1 else ""

    print(f"  📨 Telegram komut: {command} {args}")

    if command == "/tarih":
        cmd_tarih(chat_id, topic=args if args else None)
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
