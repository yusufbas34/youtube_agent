"""
Telegram Bot — YouTube Agent Komutları
/tarih  → Tarih videosu üret + yükle
/sozler → Söz videosu üret + yükle
/viral  → Tweet kontrol et + video yap + yükle
/durum  → Kanal durumları
/iptal  → Çalışan işlemi durdur
"""

import os, json, threading, time, requests, urllib3
from datetime import datetime
from pathlib import Path

# SSL uyarılarını sustur
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_bot_token():
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def get_chat_id():
    return os.environ.get("TELEGRAM_CHAT_ID", "")


def send(text: str, chat_id: str = None):
    """Telegram'a mesaj gönder."""
    token = get_bot_token()
    if not token:
        return
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


# ── Komut İşleyiciler ─────────────────────────────────────────────

_running = {}  # {"tarih": True, "sozler": False, ...}


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
            send(
                f"✅ <b>Tarih</b> yüklendi!\n"
                f"🏛 {cp['title'][:80]}\n"
                f"🔗 {result['url']}",
                chat_id
            )
        except Exception as e:
            send(f"❌ Tarih hatası: {str(e)[:200]}", chat_id)
            print(f"  ⚠ telegram cmd_tarih hata: {e}")
        finally:
            _running["tarih"] = False

    threading.Thread(target=run, daemon=True).start()


def cmd_sozler(chat_id: str):
    if _running.get("sozler"):
        send("⏳ Söz videosu zaten üretiliyor, bekle...", chat_id)
        return

    _running["sozler"] = True
    send("🎬 Söz videosu üretimi başladı...", chat_id)

    def run():
        try:
            from quotes_manager import get_next_quote, mark_quote_used
            from quote_video_generator import create_quote_video
            from uploader import run_upload
            from channel_config import SOZLER_CHANNEL_ID
            import json as _json

            quote = get_next_quote()
            if not quote:
                send("❌ Kullanılabilir söz bulunamadı!", chat_id)
                return

            send(f"📝 Söz: <i>{quote.get('text','')[:80]}</i>", chat_id)
            send("🎥 Video üretiliyor...", chat_id)

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
            mark_quote_used(quote["id"], result["url"])
            send(
                f"✅ <b>Sözler</b> yüklendi!\n"
                f"📝 {quote.get('text','')[:80]}\n"
                f"🔗 {result['url']}",
                chat_id
            )
        except Exception as e:
            send(f"❌ Sözler hatası: {str(e)[:200]}", chat_id)
            print(f"  ⚠ telegram cmd_sozler hata: {e}")
        finally:
            _running["sozler"] = False

    threading.Thread(target=run, daemon=True).start()


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
            import json as _json, re

            # Yeni tweet kontrol
            new_tweets = check_new_tweets(force=True)
            queue = load_queue()

            if not new_tweets and not queue:
                send("📭 Yeni tweet veya bekleyen video yok.", chat_id)
                return

            if new_tweets:
                added = add_to_viral_queue(new_tweets)
                send(f"📥 {len(new_tweets)} yeni tweet bulundu, {added} kuyruğa eklendi.", chat_id)
                queue = load_queue()

            # İlk bekleyen tweet'i al
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
                    meta = _json.load(f)

            raw_title = meta.get("title", item["text"][:90])
            clean_title = re.sub(r'\s*\bVideo\b\s*$', '', raw_title, flags=re.IGNORECASE).strip()
            cp = {
                "title":       clean_title[:90],
                "description": meta.get("description", "#viral #shorts"),
                "tags":        meta.get("tags", ["viral","shorts"]),
                "hashtags":    meta.get("hashtags", ["#viral","#shorts"]),
            }
            result = run_upload(cp, vpath, scheduled_time=None,
                               channel_id=VIRAL_CHANNEL_ID, channel="viral")
            send(
                f"✅ <b>Viral</b> yüklendi!\n"
                f"📱 {clean_title[:80]}\n"
                f"🔗 {result['url']}",
                chat_id
            )
        except Exception as e:
            send(f"❌ Viral hatası: {str(e)[:200]}", chat_id)
            print(f"  ⚠ telegram cmd_viral hata: {e}")
        finally:
            _running["viral"] = False

    threading.Thread(target=run, daemon=True).start()


def cmd_durum(chat_id: str):
    lines = ["📊 <b>Kanal Durumları</b>\n"]
    for ch, emoji in [("tarih","🏛"), ("sozler","📝"), ("viral","📱")]:
        durum = "🔄 Çalışıyor" if _running.get(ch) else "✅ Boşta"
        lines.append(f"{emoji} <b>{ch.capitalize()}</b>: {durum}")

    # Kaç video bekliyor
    try:
        for ch in ["sozler", "tarih", "viral"]:
            import json as _json
            p = f"data/{ch}_queue.json"
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    q = _json.load(f)
                pending = len([x for x in q if x.get("status") == "bekliyor"])
                if pending:
                    lines.append(f"   ↳ {pending} video bekliyor")
    except: pass

    lines.append(f"\n🕐 {datetime.now().strftime('%H:%M:%S')}")
    send("\n".join(lines), chat_id)


def cmd_iptal(chat_id: str):
    stopped = []
    for ch in list(_running.keys()):
        if _running.get(ch):
            _running[ch] = False
            stopped.append(ch)
    if stopped:
        send(f"🛑 Durduruldu: {', '.join(stopped)}", chat_id)
    else:
        send("ℹ️ Çalışan işlem yok.", chat_id)


def cmd_yardim(chat_id: str):
    send(
        "🤖 <b>YouTube Agent Bot</b>\n\n"
        "/tarih — Tarih videosu üret + yükle\n"
        "/tarih &lt;konu&gt; — Belirli konuda tarih videosu\n"
        "/sozler — Söz videosu üret + yükle\n"
        "/viral — Tweet kontrol et + video yap + yükle\n"
        "/durum — Kanal durumları\n"
        "/iptal — Çalışan işlemi durdur\n"
        "/yardim — Bu mesaj",
        chat_id
    )


# ── Polling Loop ──────────────────────────────────────────────────

def handle_update(update: dict):
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text    = (msg.get("text") or "").strip()

    # Sadece yetkili chat'ten komut al
    allowed = get_chat_id()
    if allowed and chat_id != allowed:
        send("⛔ Yetkisiz erişim.", chat_id)
        return

    if not text.startswith("/"):
        return

    parts   = text.split(None, 1)
    command = parts[0].lower().split("@")[0]  # /tarih@botname → /tarih
    args    = parts[1].strip() if len(parts) > 1 else ""

    print(f"  📨 Telegram komut: {command} {args}")

    if command == "/tarih":
        cmd_tarih(chat_id, topic=args if args else None)
    elif command == "/sozler":
        cmd_sozler(chat_id)
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
    """Long polling ile Telegram güncellemelerini dinle."""
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
                data = r.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        handle_update(update)
                    except Exception as e:
                        print(f"  ⚠ Update işleme hatası: {e}")
        except requests.exceptions.Timeout:
            pass  # Normal — long polling timeout
        except Exception as e:
            print(f"  ⚠ Telegram polling hata: {e}")
            time.sleep(5)


def start_bot_thread():
    """Dashboard ile aynı process'te thread olarak başlat."""
    t = threading.Thread(target=start_polling, daemon=True, name="TelegramBot")
    t.start()
    return t


if __name__ == "__main__":
    print("Telegram bot test modunda başlatılıyor...")
    start_polling()
