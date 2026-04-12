"""
Dashboard Sunucusu — Çok Kanallı
Flask ile çalışır. http://localhost:5051
"""

import os, json, threading, glob, re
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, request, send_file, send_from_directory

from quotes_manager import refresh_quotes, mark_quote_used, delete_quote
from quote_video_generator import create_quote_video
from generate_dashboard import generate_dashboard
from config import UPLOAD_TIME, UPLOAD_TIMEZONE

# Railway'de token'ları env var'lardan yükle
try:
    from token_manager import setup_tokens
    setup_tokens()
except Exception as _te:
    print(f"Token setup: {_te}")

app = Flask(__name__)

STATUS = {
    "running":   False,
    "queue":     [],
    "current":   None,
    "completed": [],
    "errors":    [],
    "log":       []
}

TARIH_STATUS = {
    "running":   False,
    "current":   None,
    "completed": [],
    "errors":    [],
    "log":       []
}


def log(msg, channel="sozler"):
    ts    = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    if channel == "tarih":
        TARIH_STATUS["log"].append(entry)
        TARIH_STATUS["log"] = TARIH_STATUS["log"][-100:]
    elif channel == "viral":
        VIRAL_STATUS["log"].append(entry)
        VIRAL_STATUS["log"] = VIRAL_STATUS["log"][-100:]
    else:
        STATUS["log"].append(entry)
        STATUS["log"] = STATUS["log"][-100:]
    print(entry)


def load_json(path, default=None):
    if default is None: default = []
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return default


def save_json(path, data):
    import shutil
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(tmp,"w",encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    shutil.move(tmp, path)


def make_scheduled_time(hour: int, minute: int = 0) -> str:
    import pytz
    tz    = pytz.timezone(UPLOAD_TIMEZONE)
    now   = datetime.now(tz)
    sched = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if sched <= now:
        sched += timedelta(days=1)
    return sched.isoformat()


# ── Upload History ─────────────────────────────────────────────────

def get_uploaded_paths(channel="sozler") -> set:
    """Yüklenen videoların yollarını döner."""
    hist = load_json(f"data/{channel}_history.json", [])
    return {h.get("video_path","") for h in hist}


def get_queued_paths(channel="sozler") -> set:
    """Sıradaki videoların yollarını döner."""
    queue = load_json(f"data/{channel}_queue.json", [])
    return {q.get("video_path","") for q in queue if q.get("status") in ("bekliyor","yukleniyor")}


def add_to_history(channel: str, video_path: str, video_id: str, url: str, title: str):
    """Yüklenen videoyu history'e ekle."""
    hist = load_json(f"data/{channel}_history.json", [])
    hist.append({
        "video_path":  video_path,
        "video_id":    video_id,
        "url":         url,
        "title":       title,
        "uploaded_at": datetime.now().isoformat()
    })
    save_json(f"data/{channel}_history.json", hist)


def remove_from_queue_by_path(channel: str, video_path: str):
    """Video yüklenince kuyruktan sil."""
    queue = load_json(f"data/{channel}_queue.json", [])
    queue = [q for q in queue if q.get("video_path") != video_path]
    save_json(f"data/{channel}_queue.json", queue)


# ── Video Üretimi ─────────────────────────────────────────────────

def produce_videos(queue: list, auto_upload: bool, scheduled_hour: int = None):
    STATUS["running"]   = True
    STATUS["completed"] = []
    STATUS["errors"]    = []

    log(f"Üretim başladı — {len(queue)} video")

    for i, quote in enumerate(queue):
        STATUS["current"] = {
            "index": i+1, "total": len(queue),
            "quote": quote.get("text","")[:60],
            "author": quote.get("author","")
        }
        log(f"Video {i+1}/{len(queue)}: {quote.get('text','')[:50]}...")

        try:
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            outpath  = f"output/sozler/quote_{ts}_{i+1}.mp4"
            Path("output/sozler").mkdir(parents=True, exist_ok=True)

            video_path = create_quote_video(quote, outpath)
            log(f"Video hazır: {outpath}")

            # Metadata kaydet
            meta = {
                "title":        (quote.get("text","")[:85] + " — " + quote.get("author","Anonim")),
                "description":  quote.get("text","") + "\n\n— " + quote.get("author","Anonim") + "\n\n#motivasyon #ozlusoz #shorts #kisiselgelisim #keşfet #viral #günlük #ilham #düşündürücü",
                "tags":         ["motivasyon","ozlusoz","shorts","kisiselgelisim","keşfet","viral","ilham","günlük","düşündürücü","sözler", quote.get("category","motivasyon")],
                "hashtags":     ["#motivasyon","#ozlusoz","#shorts","#keşfet","#viral","#ilham","#sözler","#günlük"],
                "quote_id":     quote.get("id",""),
                "quote_text":   quote.get("text",""),
                "author":       quote.get("author","Anonim"),
                "category":     quote.get("category",""),
                "channel":      "sozler",
                "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
            }
            with open(outpath.replace(".mp4",".json"),"w",encoding="utf-8") as mf:
                json.dump(meta, mf, ensure_ascii=False, indent=2)

            result = {
                "quote_id":   quote["id"],
                "quote_text": quote.get("text",""),
                "author":     quote.get("author",""),
                "video_path": video_path,
                "produced_at": datetime.now().isoformat(),
                "video_url":  None,
            }

            if auto_upload:
                log("YouTube'a yükleniyor...")
                try:
                    from uploader import run_upload
                    from upload_scheduler import make_scheduled_time as mst
                    sh = scheduled_hour
                    # "now" veya None = anlık yayınla, sayı = planla
                    if sh is None or sh == "now" or sh == "":
                        sched = None
                    else:
                        sched = mst(int(sh), 0)
                    from channel_config import SOZLER_CHANNEL_ID
                    upload = run_upload(meta, video_path, scheduled_time=sched, channel_id=SOZLER_CHANNEL_ID)
                    result["video_url"] = upload["url"]
                    result["video_id"]  = upload["video_id"]
                    # Söz kullanıldı kaydet
                    mark_quote_used(quote["id"], upload["url"])
                    # History'e ekle
                    add_to_history("sozler", video_path, upload.get("video_id",""), upload["url"], meta["title"])
                    log(f"Yüklendi: {upload['url']}")
                except Exception as e:
                    log(f"Yukleme hatasi: {str(e)}")
                    result["upload_error"] = str(e)
                    mark_quote_used(quote["id"])
            else:
                # Sadece üret - söz kullanıldı kaydet
                mark_quote_used(quote["id"])

            STATUS["completed"].append(result)

        except Exception as e:
            log(f"HATA: {str(e)}")
            STATUS["errors"].append({"quote": quote.get("text","")[:50], "error": str(e)})

    generate_dashboard()
    STATUS["running"] = False
    STATUS["current"] = None
    log(f"Tamamlandı! {len(STATUS['completed'])} video, {len(STATUS['errors'])} hata")


# ── Ana Endpoint'ler ──────────────────────────────────────────────

@app.route("/")
def index():
    generate_dashboard()
    return send_file("dashboard.html")


@app.route("/api/status")
def api_status():
    return jsonify(STATUS)


@app.route("/api/tarih/status")
def api_tarih_status():
    return jsonify(TARIH_STATUS)


@app.route("/api/quotes")
def api_quotes():
    return jsonify(load_json("quotes.json", []))


@app.route("/api/refresh-quotes", methods=["POST"])
def api_refresh():
    try:
        quotes = refresh_quotes(force=True)
        generate_dashboard()
        return jsonify({"ok": True, "count": len(quotes)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/produce", methods=["POST"])
def api_produce():
    if STATUS["running"]:
        return jsonify({"ok": False, "error": "Zaten çalışıyor"}), 400
    data = request.json or {}
    queue = data.get("queue", [])
    if not queue:
        return jsonify({"ok": False, "error": "Söz listesi boş"}), 400
    STATUS["queue"] = queue
    STATUS["log"]   = []
    t = threading.Thread(
        target=produce_videos,
        args=(queue, data.get("auto_upload",False), data.get("scheduled_hour",None)),
        daemon=True
    )
    t.start()
    return jsonify({"ok": True, "message": f"{len(queue)} video üretimi başladı"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    STATUS["running"] = False
    log("Durdurma sinyali gönderildi")
    return jsonify({"ok": True})


# ── Söz Endpoint'leri ─────────────────────────────────────────────

@app.route("/api/delete-quote", methods=["POST"])
def api_delete_quote():
    data = request.json or {}
    qid  = data.get("id")
    if not qid:
        return jsonify({"ok": False, "error": "ID gerekli"}), 400
    try:
        delete_quote(qid)
        generate_dashboard()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/add-quote", methods=["POST"])
def api_add_quote():
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Söz metni boş"}), 400
    try:
        from quotes_manager import load_quotes, save_quotes
        quotes = load_quotes()
        new_q  = {
            "id":         "q_manual_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            "text":       text,
            "author":     data.get("author","Anonim"),
            "category":   data.get("category","motivasyon"),
            "source":     "manuel",
            "viral_score": int(data.get("viral_score",7)),
            "original":   None,
            "used":       False,
            "used_at":    None,
            "video_url":  None,
            "created_at": datetime.now().isoformat()
        }
        quotes.insert(0, new_q)
        save_quotes(quotes)
        generate_dashboard()
        return jsonify({"ok": True, "id": new_q["id"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Sözler Kanalı — Üretilen Videolar ─────────────────────────────

@app.route("/api/local-videos")
def api_local_videos():
    uploaded = get_uploaded_paths("sozler")
    queued   = get_queued_paths("sozler")
    videos   = []
    for f in sorted(glob.glob("output/sozler/quote_*.mp4"), reverse=True):
        if f in uploaded or f in queued:
            continue
        size_mb = round(os.path.getsize(f)/(1024*1024), 1)
        basename = os.path.basename(f)
        meta = {}
        mp = f.replace(".mp4",".json")
        if os.path.exists(mp):
            try:
                with open(mp,"r",encoding="utf-8") as mf: meta = json.load(mf)
            except: pass
        videos.append({
            "path": f, "filename": basename, "size_mb": size_mb,
            "url": f"/output/sozler/{basename}",
            "title":        meta.get("title",""),
            "description":  meta.get("description",""),
            "tags":         meta.get("tags",[]),
            "quote_text":   meta.get("quote_text",""),
            "author":       meta.get("author",""),
            "quote_id":     meta.get("quote_id",""),
            "generated_at": meta.get("generated_at",""),
        })
    return jsonify({"ok": True, "videos": videos})


@app.route("/api/upload-local", methods=["POST"])
def api_upload_local():
    if STATUS["running"]:
        return jsonify({"ok": False, "error": "Zaten çalışıyor"}), 400
    data           = request.json or {}
    video_path     = data.get("video_path","")
    raw_hour       = data.get("scheduled_hour", None)
    scheduled_hour = None if (raw_hour is None or raw_hour == "now" or raw_hour == "") else int(raw_hour)
    instant        = (raw_hour is None or raw_hour == "now")
    channel        = data.get("channel","sozler")
    if not video_path or not os.path.exists(video_path):
        return jsonify({"ok": False, "error": "Dosya bulunamadı"}), 400

    # ── Tekrar yükleme kontrolü ──
    uploaded = get_uploaded_paths(channel)
    if os.path.normpath(video_path) in {os.path.normpath(p) for p in uploaded}:
        return jsonify({"ok": False, "error": "Bu video zaten yüklendi!"}), 400

    # Kanal bazlı STATUS
    _status = TARIH_STATUS if channel == "tarih" else STATUS

    def do_upload():
        from channel_config import CHANNELS
        from uploader import run_upload
        _status["running"] = True
        _status["errors"]  = []
        log(f"Yukleme basladi: {os.path.basename(video_path)}", channel)
        try:
            h, m  = map(int, UPLOAD_TIME.split(":"))
            # Saat seçilmişse planla, "Varsayılan" seçilmişse hemen yükle
            sched = None if instant else (make_scheduled_time(scheduled_hour, 0) if scheduled_hour else None)
            meta  = {}
            mp    = video_path.replace(".mp4",".json")
            if os.path.exists(mp):
                with open(mp,"r",encoding="utf-8") as mf: meta = json.load(mf)
            ch_id = CHANNELS.get(channel, CHANNELS.get("sozler",{})).get("channel_id")
            log(f"Kanal: {channel} ID: {ch_id}", channel)
            cp = {
                "title":       (meta.get("title") or os.path.basename(video_path))[:90],
                "description": meta.get("description","") or "#shorts",
                "tags":        meta.get("tags",[]) or ["shorts"],
                "hashtags":    meta.get("hashtags",[]) or ["#shorts"],
            }
            result = run_upload(cp, video_path, scheduled_time=sched, channel_id=ch_id, channel=channel)
            url    = result["url"]
            add_to_history(channel, video_path, result.get("video_id",""), url, cp["title"])
            remove_from_queue_by_path(channel, video_path)
            qid = meta.get("quote_id","")
            if qid: mark_quote_used(qid, url)
            log(f"Yuklendi: {url}", channel)
            _status["completed"].append({"quote_text": cp["title"], "video_url": url})
            generate_dashboard()
        except Exception as e:
            log(f"Yukleme hatasi: {str(e)}", channel)
            _status["errors"].append({"quote": os.path.basename(video_path), "error": str(e)})
        finally:
            _status["running"] = False
    threading.Thread(target=do_upload, daemon=True).start()
    return jsonify({"ok": True, "message": "Yükleme başladı"})


# ── Kuyruk Endpoint'leri ──────────────────────────────────────────

@app.route("/api/queue")
def api_queue():
    channel = request.args.get("channel","sozler")
    queue   = load_json(f"data/{channel}_queue.json", [])
    stats   = {
        "bekliyor":   len([q for q in queue if q.get("status")=="bekliyor"]),
        "yukleniyor": len([q for q in queue if q.get("status")=="yukleniyor"]),
        "yuklendi":   len([q for q in queue if q.get("status")=="yuklendi"]),
        "hata":       len([q for q in queue if q.get("status")=="hata"]),
    }
    # Yüklenenler dashboard'da gözükmesin
    visible = [q for q in queue if q.get("status") != "yuklendi"]
    return jsonify({"ok": True, "queue": visible, "stats": stats})


@app.route("/api/queue/add", methods=["POST"])
def api_queue_add():
    data    = request.json or {}
    channel = data.get("channel","sozler")
    try:
        queue = load_json(f"data/{channel}_queue.json", [])
        item  = {
            "id":         f"qi_{datetime.now().strftime('%Y%m%d%H%M%S%f')[-12:]}",
            "type":       data.get("type","video"),
            "status":     "bekliyor",
            "video_path": data.get("video_path",""),
            "title":      data.get("title",""),
            "author":     data.get("author",""),
            "quote_id":   data.get("quote_id",""),
            "added_at":   datetime.now().isoformat(),
            "video_url":  None,
            "error":      None,
        }
        queue.append(item)
        save_json(f"data/{channel}_queue.json", queue)
        generate_dashboard()
        return jsonify({"ok": True, "item": item})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/queue/remove", methods=["POST"])
def api_queue_remove():
    data    = request.json or {}
    channel = data.get("channel","sozler")
    qid     = data.get("id","")
    try:
        queue = load_json(f"data/{channel}_queue.json", [])
        queue = [q for q in queue if q.get("id") != qid]
        save_json(f"data/{channel}_queue.json", queue)
        generate_dashboard()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/queue/reorder", methods=["POST"])
def api_queue_reorder():
    data    = request.json or {}
    channel = data.get("channel","sozler")
    order   = data.get("order",[])
    try:
        queue  = load_json(f"data/{channel}_queue.json", [])
        id_map = {q["id"]: q for q in queue}
        reordered = [id_map[i] for i in order if i in id_map]
        remaining = [q for q in queue if q["id"] not in order]
        save_json(f"data/{channel}_queue.json", reordered + remaining)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/queue/upload-now", methods=["POST"])
def api_queue_upload_now():
    if STATUS["running"]:
        return jsonify({"ok": False, "error": "Zaten çalışıyor"}), 400
    data = request.json or {}
    try:
        from upload_scheduler import do_scheduled_upload, is_company_network
        if is_company_network():
            return jsonify({"ok": False, "error": "Şirket ağında yükleme yapılamaz"}), 400
        STATUS["log"] = []
        threading.Thread(target=do_scheduled_upload, daemon=True).start()
        return jsonify({"ok": True, "message": "Yükleme başladı"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Ağ Durumu ─────────────────────────────────────────────────────

@app.route("/api/network-status")
def api_network_status():
    try:
        from upload_scheduler import is_company_network, get_local_ip
        ip = get_local_ip()
        company = is_company_network()
        return jsonify({"ok": True, "ip": ip, "is_company": company, "can_upload": not company})
    except Exception as e:
        return jsonify({"ok": True, "ip": "?", "is_company": False, "can_upload": True})


# ── Canlı İstatistikler ───────────────────────────────────────────

@app.route("/api/live-stats")
def api_live_stats():
    try:
        from uploader import get_authenticated_service
        history = load_json("data/sozler_history.json", []) or load_json("upload_history.json", [])
        if not history:
            return jsonify({"ok": True, "stats": {}})
        youtube   = get_authenticated_service()
        video_ids = [h["video_id"] for h in history if h.get("video_id")]
        if not video_ids:
            return jsonify({"ok": True, "stats": {}})
        stats = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            resp  = youtube.videos().list(part="statistics,snippet", id=",".join(batch)).execute()
            for item in resp.get("items",[]):
                s = item.get("statistics",{})
                stats[item["id"]] = {
                    "title":    item["snippet"]["title"],
                    "views":    int(s.get("viewCount",0)),
                    "likes":    int(s.get("likeCount",0)),
                    "comments": int(s.get("commentCount",0)),
                }
        return jsonify({"ok": True, "stats": stats})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Yol Haritası ──────────────────────────────────────────────────

@app.route("/api/roadmap")
def api_roadmap():
    """Her iki kanal için analytics analizi ve yol haritası üretir."""
    try:
        import httpx
        import anthropic
        from config import ANTHROPIC_API_KEY

        # Sözler kanalı verilerini topla
        sozler_hist  = load_json("data/sozler_history.json", []) or load_json("upload_history.json", [])
        sozler_used  = load_json("used_quotes.json", [])
        sozler_del   = load_json("deleted_quotes.json", [])
        sozler_queue = load_json("data/sozler_queue.json", [])

        # Tarih kanalı verilerini topla
        tarih_hist    = load_json("data/tarih_history.json", [])
        tarih_anal    = load_json("data/tarih_analytics.json", {})

        # Canlı stats topla
        live_stats = {}
        try:
            from uploader import get_authenticated_service
            all_ids = [h["video_id"] for h in sozler_hist + tarih_hist if h.get("video_id")]
            if all_ids:
                yt = get_authenticated_service()
                for i in range(0, len(all_ids), 50):
                    batch = all_ids[i:i+50]
                    resp = yt.videos().list(part="statistics,snippet", id=",".join(batch)).execute()
                    for item in resp.get("items",[]):
                        s = item.get("statistics",{})
                        live_stats[item["id"]] = {
                            "title":    item["snippet"]["title"],
                            "views":    int(s.get("viewCount",0)),
                            "likes":    int(s.get("likeCount",0)),
                            "comments": int(s.get("commentCount",0)),
                        }
        except: pass

        # Prompt için veri hazırla
        sozler_summary = {
            "total_videos":   len(sozler_hist),
            "total_views":    sum(live_stats.get(h.get("video_id",""),{}).get("views",0) for h in sozler_hist),
            "total_likes":    sum(live_stats.get(h.get("video_id",""),{}).get("likes",0) for h in sozler_hist),
            "used_quotes":    len(sozler_used),
            "deleted_quotes": len(sozler_del),
            "queue_size":     len([q for q in sozler_queue if q.get("status")=="bekliyor"]),
            "top_videos":     sorted(
                [{"title":h.get("title",""), "views":live_stats.get(h.get("video_id",""),{}).get("views",0)} for h in sozler_hist],
                key=lambda x: x["views"], reverse=True
            )[:5],
        }

        tarih_summary = {
            "total_videos": len(tarih_hist),
            "total_views":  sum(live_stats.get(h.get("video_id",""),{}).get("views",0) for h in tarih_hist),
            "formats":      tarih_anal.get("formats",{}),
        }

        http   = httpx.Client(verify=False)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)

        prompt = f"""
Sen bir YouTube kanal stratejisti ve veri analistisin.

SÖZLER KANALI VERİLERİ:
{json.dumps(sozler_summary, ensure_ascii=False, indent=2)}

TARİH KANALI VERİLERİ:
{json.dumps(tarih_summary, ensure_ascii=False, indent=2)}

Bu verilere dayanarak her iki kanal için detaylı bir yol haritası ve aksiyon planı üret.

Sadece JSON döndür:
{{
  "sozler": {{
    "ozet": "Kısa değerlendirme (2-3 cümle)",
    "guclu_yonler": ["güçlü yön 1", "güçlü yön 2"],
    "zayif_yonler": ["zayıf yön 1", "zayıf yön 2"],
    "hemen_yapilacaklar": [
      {{"oncelik": "YUKSEK", "aksiyon": "aksiyon açıklaması", "beklenen_etki": "etki"}}
    ],
    "bu_hafta": [
      {{"aksiyon": "aksiyon", "detay": "detay"}}
    ],
    "bu_ay": [
      {{"aksiyon": "aksiyon", "detay": "detay"}}
    ],
    "icerik_onerileri": ["öneri 1", "öneri 2", "öneri 3"],
    "optimizasyon_ipuclari": ["ipucu 1", "ipucu 2"]
  }},
  "tarih": {{
    "ozet": "Kısa değerlendirme",
    "en_iyi_format": "hangi format daha iyi çalışıyor ve neden",
    "hemen_yapilacaklar": [
      {{"oncelik": "YUKSEK", "aksiyon": "aksiyon", "beklenen_etki": "etki"}}
    ],
    "bu_hafta": [{{"aksiyon": "aksiyon", "detay": "detay"}}],
    "bu_ay": [{{"aksiyon": "aksiyon", "detay": "detay"}}],
    "icerik_onerileri": ["konu önerisi 1", "konu önerisi 2", "konu önerisi 3"],
    "optimizasyon_ipuclari": ["ipucu 1", "ipucu 2"]
  }},
  "genel": {{
    "toplam_kanal_degerlendirme": "genel değerlendirme",
    "kritik_aksiyon": "en acil yapılması gereken şey"
  }},
  "guncellendi": "{datetime.now().strftime('%d.%m.%Y %H:%M')}"
}}
"""

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role":"user","content":prompt}]
        )
        text = msg.content[0].text.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        elif "```" in text:   text = text.split("```")[1].split("```")[0]
        roadmap = json.loads(text.strip())

        # Cache'e kaydet
        save_json("data/roadmap_cache.json", roadmap)
        return jsonify({"ok": True, "roadmap": roadmap})
    except Exception as e:
        # Cache'den döndür
        cached = load_json("data/roadmap_cache.json", {})
        if cached:
            return jsonify({"ok": True, "roadmap": cached, "cached": True})
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Tarih Kanalı ──────────────────────────────────────────────────

@app.route("/api/tarih/generate", methods=["POST"])
def api_tarih_generate():
    if STATUS["running"]:
        return jsonify({"ok": False, "error": "Zaten çalışıyor"}), 400
    data = request.json or {}

    def do_generate():
        TARIH_STATUS["running"]   = True
        TARIH_STATUS["log"]       = []
        TARIH_STATUS["completed"] = []
        TARIH_STATUS["errors"]    = []
        log("Tarih videosu üretimi başladı...", "tarih")
        try:
            from history_content_generator import generate_history_content, get_best_format
            from history_video_generator import create_history_video

            analytics = load_json("data/tarih_analytics.json", {})
            fmt = data.get("format","auto")
            if fmt == "auto":
                fmt = get_best_format(analytics)
            log(f"Format: {fmt}", "tarih")

            content = generate_history_content(topic=data.get("topic"), format_type=fmt)
            log(f"Icerik: {content['title'][:60]}", "tarih")

            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = f"output/tarih/tarih_{ts}.mp4"
            video_path = create_history_video(content, out)
            log(f"Video hazir: {os.path.basename(video_path)}", "tarih")

            result = {"video_path": video_path, "title": content["title"],
                      "format": fmt, "quote_text": content["title"], "video_url": None}

            if data.get("auto_upload"):
                # Tarih kanalı credentials kontrolü
                # token_tarih.json varsa yükle
                if not os.path.exists("token_tarih.json"):
                    log("⚠ Tarih kanali token bulunamadi. python create_tarih_token.py calistir!", "tarih")
                    log("✅ Video yerel kaydedildi, Uretilen Videolar sekmesinden yukle", "tarih")
                else:
                    try:
                        from uploader import run_upload
                        sh = data.get("scheduled_hour")
                        # now veya boş = anlık yayınla, saat varsa planla
                        sched = None if (not sh or sh == "now") else make_scheduled_time(int(sh), 0)
                        meta  = load_json(video_path.replace(".mp4",".json"), {})
                        cp = {
                            "title":       meta.get("title", content["title"])[:90],
                            "description": meta.get("description", content.get("description","")),
                            "tags":        meta.get("tags", content.get("tags",[])),
                            "hashtags":    meta.get("hashtags", content.get("hashtags",[])),
                        }
                        from channel_config import TARIH_CHANNEL_ID
                        upload = run_upload(cp, video_path, scheduled_time=sched, channel_id=TARIH_CHANNEL_ID, channel="tarih")
                        result["video_url"] = upload["url"]
                        add_to_history("tarih", video_path, upload.get("video_id",""), upload["url"], cp["title"])
                        remove_from_queue_by_path("tarih", video_path)
                        log(f"Yüklendi: {upload['url']}", "tarih")
                        from history_content_generator import update_format_analytics
                        update_format_analytics(fmt, 0, 0)
                    except Exception as e:
                        log(f"Yükleme hatası: {str(e)}", "tarih")
                        import traceback; traceback.print_exc()

            TARIH_STATUS["completed"].append(result)
            STATUS["completed"] = []  # Sözler log'unu temizle
            generate_dashboard()
        except Exception as e:
            log(f"HATA: {str(e)}", "tarih")
            import traceback; traceback.print_exc()
            TARIH_STATUS["errors"].append({"quote": "tarih", "error": str(e)})
        finally:
            TARIH_STATUS["running"] = False

    threading.Thread(target=do_generate, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/tarih/local-videos")
def api_tarih_local_videos():
    uploaded = {os.path.normpath(p) for p in get_uploaded_paths("tarih")}
    queued   = {os.path.normpath(p) for p in get_queued_paths("tarih")}
    videos   = []
    for f in sorted(glob.glob("output/tarih/tarih_*.mp4"), reverse=True):
        nf = os.path.normpath(f)
        is_uploaded = nf in uploaded
        if nf in queued: continue
        size_mb  = round(os.path.getsize(f)/(1024*1024), 1)
        basename = os.path.basename(f)
        meta = {}
        mp = f.replace(".mp4",".json")
        if os.path.exists(mp):
            try:
                with open(mp,"r",encoding="utf-8") as mf: meta = json.load(mf)
            except: pass
        videos.append({
            "path":        f, "filename": basename, "size_mb": size_mb,
            "url":         f"/output/tarih/{basename}",
            "title":       meta.get("title",""),
            "period":      meta.get("period",""),
            "format":      meta.get("format",""),
            "topic":       meta.get("topic",""),
            "generated_at":meta.get("generated_at",""),
            "uploaded":    is_uploaded,
            "video_url":   next((h.get("url") for h in load_json("data/tarih_history.json",[])
                                if os.path.normpath(h.get("video_path",""))==nf), None),
        })
    return jsonify({"ok": True, "videos": videos})


# ── Static dosyalar ───────────────────────────────────────────────

@app.route("/output/sozler/<path:filename>")
def serve_sozler_output(filename):
    return send_from_directory("output/sozler", filename)


@app.route("/output/tarih/<path:filename>")
def serve_tarih_output(filename):
    return send_from_directory("output/tarih", filename)


# Eski output yolu uyumluluğu
@app.route("/output/<path:filename>")
def serve_output(filename):
    # Önce sozler'de ara
    for d in ["output/sozler", "output/tarih", "output"]:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return send_from_directory(d, filename)
    return "Not found", 404


# ── Başlat ────────────────────────────────────────────────────────


@app.route("/api/roadmap/tarih")
def api_roadmap_tarih():
    """Tarih kanalı için özel yol haritası üretir."""
    use_cache = request.args.get("cache") == "1"
    if use_cache:
        cached = load_json("data/tarih_roadmap_cache.json", {})
        if cached: return jsonify({"ok": True, "roadmap": cached, "cached": True})

    try:
        import httpx, anthropic
        from config import ANTHROPIC_API_KEY

        tarih_hist = load_json("data/tarih_history.json", [])
        tarih_anal = load_json("data/tarih_analytics.json", {})
        live_stats = {}
        try:
            from uploader import get_authenticated_service
            ids = [h["video_id"] for h in tarih_hist if h.get("video_id")]
            if ids:
                yt = get_authenticated_service()
                for i in range(0, len(ids), 50):
                    resp = yt.videos().list(part="statistics,snippet", id=",".join(ids[i:i+50])).execute()
                    for item in resp.get("items",[]):
                        s = item.get("statistics",{})
                        live_stats[item["id"]] = {"views":int(s.get("viewCount",0)),"likes":int(s.get("likeCount",0))}
        except: pass

        summary = {
            "total_videos": len(tarih_hist),
            "total_views":  sum(live_stats.get(h.get("video_id",""),{}).get("views",0) for h in tarih_hist),
            "formats":      tarih_anal.get("formats",{}),
        }

        http   = httpx.Client(verify=False)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)
        prompt = f"""Tarih YouTube kanalı stratejisti. Bu veriler: {json.dumps(summary, ensure_ascii=False)}
Sadece JSON döndür:
{{"tarih":{{"ozet":"değerlendirme","en_iyi_format":"format analizi","hemen_yapilacaklar":[{{"oncelik":"YUKSEK","aksiyon":"aksiyon","beklenen_etki":"etki"}}],"bu_hafta":[{{"aksiyon":"a","detay":"d"}}],"bu_ay":[{{"aksiyon":"a","detay":"d"}}],"icerik_onerileri":["k1","k2","k3","k4","k5"],"optimizasyon_ipuclari":["i1","i2","i3"]}},"guncellendi":"{datetime.now().strftime('%d.%m.%Y %H:%M')}"}}"""

        msg  = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=2000, messages=[{"role":"user","content":prompt}])
        text = msg.content[0].text.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        elif "```" in text:   text = text.split("```")[1].split("```")[0]
        roadmap = json.loads(text.strip())
        save_json("data/tarih_roadmap_cache.json", roadmap)
        return jsonify({"ok": True, "roadmap": roadmap})
    except Exception as e:
        cached = load_json("data/tarih_roadmap_cache.json", {})
        if cached: return jsonify({"ok": True, "roadmap": cached, "cached": True})
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Viral Kanal Endpoint'leri ──────────────────────────────────────

VIRAL_STATUS = {"running":False,"log":[],"completed":[],"errors":[]}

@app.route("/api/viral/status")
def api_viral_status():
    return jsonify(VIRAL_STATUS)

@app.route("/api/viral/check", methods=["POST"])
def api_viral_check():
    """Yeni tweet'leri kontrol et ve kuyruğa ekle."""
    try:
        data  = request.json or {}
        force = data.get("force", False)
        from viral_scraper import check_new_tweets, add_to_viral_queue
        new_tweets = check_new_tweets(force=force)
        added = add_to_viral_queue(new_tweets) if new_tweets else 0
        return jsonify({"ok":True,"new":len(new_tweets),"added":added,"force":force})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}),500

@app.route("/api/viral/queue")
def api_viral_queue():
    queue = load_json("data/viral_queue.json",[])
    visible = [q for q in queue if q.get("status") not in ("yuklendi",)]
    return jsonify({"ok":True,"queue":visible})


@app.route("/api/viral/download-video", methods=["POST"])
def api_viral_download_video():
    """Seçilen tweet videosunu yt-dlp ile indirir."""
    data     = request.json or {}
    tweet_id = data.get("tweet_id","")
    if not tweet_id:
        return jsonify({"ok":False,"error":"tweet_id gerekli"}),400
    try:
        from viral_scraper import YTDLP_PATH, OUTPUT_DIR
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = str(OUTPUT_DIR / f"tweet_{tweet_id}.mp4")

        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            queue = load_json("data/viral_queue.json",[])
            for q in queue:
                if q.get("tweet_id") == tweet_id:
                    q["has_video"] = True
                    q["video_path"] = out_path
            save_json("data/viral_queue.json", queue)
            return jsonify({"ok":True,"url":f"/output/viral/tweet_{tweet_id}.mp4","cached":True})

        tweet_url = f"https://x.com/tirajnews/status/{tweet_id}"
        cmd = [YTDLP_PATH,"--no-check-certificate","-f","mp4/best[ext=mp4]/best",
               "--no-playlist","-o",out_path,"--quiet","--no-warnings", tweet_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            queue = load_json("data/viral_queue.json",[])
            for q in queue:
                if q.get("tweet_id") == tweet_id:
                    q["has_video"]  = True
                    q["video_path"] = out_path
            save_json("data/viral_queue.json", queue)
            return jsonify({"ok":True,"url":f"/output/viral/tweet_{tweet_id}.mp4"})
        else:
            return jsonify({"ok":False,"error":"Video indirilemedi (tweet'te video olmayabilir)"}),400
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}),500


@app.route("/api/viral/produce", methods=["POST"])
def api_viral_produce():
    """Kuyruktaki tweet'leri video yap."""
    if VIRAL_STATUS["running"]:
        return jsonify({"ok":False,"error":"Zaten çalışıyor"}),400
    
    data        = request.json or {}
    item_ids    = data.get("ids",[])
    auto_upload = data.get("auto_upload", False)
    sched_hour  = data.get("scheduled_hour", None)   # None = anlık
    instant     = data.get("instant", True)           # True = anlık yayınla

    def do_produce():
        VIRAL_STATUS["running"]   = True
        VIRAL_STATUS["log"]       = []
        VIRAL_STATUS["completed"] = []
        VIRAL_STATUS["errors"]    = []

        queue = load_json("data/viral_queue.json",[])
        items = [q for q in queue if q.get("status")=="bekliyor"]
        if item_ids:
            items = [q for q in items if q.get("id") in item_ids]

        log(f"Viral üretim: {len(items)} tweet", "viral")
        
        for item in items:
            try:
                from viral_video_generator import create_viral_video
                ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
                out = f"output/viral/viral_{ts}.mp4"
                
                vpath = create_viral_video(item, out)
                if not vpath:
                    log(f"Video yok, atlandı: {item['text'][:40]}", "viral")
                    item["status"] = "atlandi"
                    continue

                item["video_path"] = vpath
                item["status"]     = "uretildi"
                log(f"Hazır: {os.path.basename(vpath)}", "viral")

                if auto_upload:
                    try:
                        from uploader import run_upload
                        from channel_config import VIRAL_CHANNEL_ID
                        # Anlık veya planlı
                        sched = None if (instant or sched_hour is None) else make_scheduled_time(sched_hour, 0)
                        meta = load_json(vpath.replace(".mp4",".json"),{})
                        # Başlık sonundaki "Video" kelimesini temizle
                        raw_title = meta.get("title", item["text"][:90])
                        clean_title = re.sub(r'\s*\bVideo\b\s*$','', raw_title, flags=re.IGNORECASE).strip()
                        cp = {
                            "title":       clean_title[:90],
                            "description": meta.get("description","#viral #shorts"),
                            "tags":        meta.get("tags",["viral","shorts","gundem","trending"]),
                            "hashtags":    meta.get("hashtags",["#viral","#shorts","#gundem"]),
                        }
                        result = run_upload(cp, vpath, scheduled_time=sched, channel="viral")
                        item["status"]    = "yuklendi"
                        item["video_url"] = result["url"]
                        add_to_history("viral", vpath, result.get("video_id",""),
                                      result["url"], cp["title"])
                        log(f"Yüklendi: {result['url']}", "viral")
                    except Exception as e:
                        log(f"Yükleme hatası: {str(e)}", "viral")

                VIRAL_STATUS["completed"].append({
                    "text": item["text"][:60],
                    "video_path": vpath,
                    "video_url": item.get("video_url"),
                })
            except Exception as e:
                log(f"Hata: {str(e)}", "viral")
                item["status"] = "hata"
                VIRAL_STATUS["errors"].append({"text":item["text"][:40],"error":str(e)})

        save_json("data/viral_queue.json", queue)
        generate_dashboard()
        VIRAL_STATUS["running"] = False
        log(f"Tamamlandı: {len(VIRAL_STATUS['completed'])} video", "viral")

    threading.Thread(target=do_produce, daemon=True).start()
    return jsonify({"ok":True})

@app.route("/api/viral/local-videos")
def api_viral_local_videos():
    uploaded = {os.path.normpath(p) for p in get_uploaded_paths("viral")}
    queued   = {os.path.normpath(p) for p in get_queued_paths("viral")}
    videos   = []
    for f in sorted(glob.glob("output/viral/viral_*.mp4"), reverse=True):
        nf = os.path.normpath(f)
        is_uploaded = nf in uploaded
        if nf in queued: continue  # sıradakini gösterme
        size_mb  = round(os.path.getsize(f)/(1024*1024),1)
        basename = os.path.basename(f)
        meta = {}
        mp = f.replace(".mp4",".json")
        if os.path.exists(mp):
            try:
                with open(mp,"r",encoding="utf-8") as mf: meta=json.load(mf)
            except: pass
        videos.append({
            "path":        f,
            "filename":    basename,
            "size_mb":     size_mb,
            "url":         f"/output/viral/{basename}",
            "title":       meta.get("title",""),
            "source":      meta.get("source",""),
            "generated_at":meta.get("generated_at",""),
            "uploaded":    is_uploaded,
            "video_url":   next((h.get("url") for h in load_json("data/viral_history.json",[])
                                if os.path.normpath(h.get("video_path",""))==nf), None),
        })
    return jsonify({"ok":True,"videos":videos})

@app.route("/output/viral/<path:filename>")
def serve_viral_output(filename):
    return send_from_directory("output/viral", filename)

if __name__ == "__main__":
    for d in ["output/sozler", "output/tarih", "data", "music_cache"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("  YouTube AI Agent Dashboard")
    print("  http://localhost:5051")
    print("  Durdurmak için Ctrl+C")
    print("=" * 50)

    generate_dashboard()

    try:
        from upload_scheduler import start_scheduler, is_company_network, get_local_ip
        ip = get_local_ip()
        company = is_company_network()
        print(f"  Yerel IP: {ip}")
        print(f"  Ağ: {'Şirket ağı (yükleme kapalı)' if company else 'Ev/dış ağ (yükleme aktif)'}")
        scheduler = start_scheduler()
        print(f"  Zamanlayıcı: her gün {UPLOAD_TIME}")
    except Exception as e:
        print(f"  Zamanlayıcı başlatılamadı: {str(e)}")

    print("=" * 50)
    port = int(os.environ.get("PORT", 5051))
    app.run(host="0.0.0.0", port=port, debug=False)
