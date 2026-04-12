"""
Yükleme Zamanlayıcı
- Her gün belirlenen saatte kuyruktaki sıradaki videoyu yükler
- Şirket ağı kontrolü yapar, şirket ağındaysa bekler
- upload_queue.json'daki sırayı takip eder
"""

import os, json, time, socket, logging
from datetime import datetime, timedelta
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import UPLOAD_TIME, UPLOAD_TIMEZONE

QUEUE_FILE   = "upload_queue.json"
LOG_FILE     = "scheduler.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("scheduler")

# Şirket ağı tespiti — bu IP/hostname'leri kendi ağına göre düzenle
COMPANY_NETWORK_HINTS = [
    "10.60.",      # Şirket ağı IP aralığı (ekrandan gördüğümüz: 10.60.174.211)
    "10.0.",
    "172.16.",
]


def get_local_ip() -> str:
    """Bilgisayarın yerel IP adresini döner."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"


def is_company_network() -> bool:
    """Şirket ağında mı kontrol eder."""
    ip = get_local_ip()
    for hint in COMPANY_NETWORK_HINTS:
        if ip.startswith(hint):
            log.info(f"Şirket ağı tespit edildi: {ip} — yükleme atlanıyor")
            return True
    log.info(f"Ev/dış ağ: {ip} — yükleme yapılabilir")
    return False


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_queue() -> list:
    return load_json(QUEUE_FILE)

def save_queue(q: list):
    save_json(QUEUE_FILE, q)


def get_next_in_queue() -> dict | None:
    """Kuyruktaki sıradaki bekleyen öğeyi döner."""
    queue = load_queue()
    for item in queue:
        if item.get("status") == "bekliyor":
            return item
    return None


def mark_queue_item(item_id: str, status: str, video_url: str = None, error: str = None):
    """Kuyruk öğesinin durumunu günceller."""
    queue = load_queue()
    for item in queue:
        if item.get("id") == item_id:
            item["status"]     = status
            item["updated_at"] = datetime.now().isoformat()
            if video_url: item["video_url"] = video_url
            if error:     item["error"]     = error
            break
    save_queue(queue)


def make_scheduled_time(hour: int, minute: int = 0) -> str:
    """Bugün için yayın zamanı döner."""
    import pytz
    tz    = pytz.timezone(UPLOAD_TIMEZONE)
    now   = datetime.now(tz)
    sched = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # Eğer saat geçtiyse yarın
    if sched <= now:
        sched += timedelta(days=1)
    return sched.isoformat()


def do_scheduled_upload():
    """Zamanlanmış yükleme işlemi."""
    log.info("=" * 40)
    log.info("Zamanlanmış yükleme başladı")

    # Şirket ağı kontrolü
    if is_company_network():
        log.info("Şirket ağı — yükleme atlandı, yarın tekrar denenecek")
        return

    # Kuyruktaki sıradaki öğeyi al
    item = get_next_in_queue()
    if not item:
        log.info("Kuyruk boş — yüklenecek içerik yok")
        return

    log.info(f"Yüklenecek: {item.get('title','?')[:60]}")
    mark_queue_item(item["id"], "yukleniyor")

    try:
        from uploader import run_upload
        from quotes_manager import mark_quote_used

        # Video dosyası kontrolü
        video_path = item.get("video_path","")
        if not video_path or not os.path.exists(video_path):
            raise FileNotFoundError(f"Video bulunamadı: {video_path}")

        # Yayın saatini hesapla
        h, m = map(int, UPLOAD_TIME.split(":"))
        sched = make_scheduled_time(h, m)

        # Metadata json varsa oku
        meta_path = video_path.replace(".mp4", ".json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                import json as _json
                with open(meta_path,"r",encoding="utf-8") as mf:
                    meta = _json.load(mf)
            except: pass

        content_plan = {
            "title":       (meta.get("title") or item.get("title","Ozlu Soz"))[:90],
            "description": meta.get("description") or (item.get("title","") + "\n\n#motivasyon #ozlusoz #shorts"),
            "tags":        meta.get("tags") or ["motivasyon","ozlusoz","shorts","kisiselgelisim"],
            "hashtags":    meta.get("hashtags") or ["#motivasyon","#ozlusoz","#shorts"]
        }

        result = run_upload(content_plan, video_path, scheduled_time=sched)
        url    = result["url"]

        # Kuyruğu güncelle
        mark_queue_item(item["id"], "yuklendi", video_url=url)
        log.info(f"✅ Yüklendi: {url}")

        # Söz kullanıldı olarak işaretle
        quote_id = item.get("quote_id")
        if quote_id:
            mark_quote_used(quote_id, url)

        # Dashboard güncelle
        try:
            from generate_dashboard import generate_dashboard
            generate_dashboard()
        except: pass

    except Exception as e:
        log.error(f"❌ Yükleme hatası: {e}")
        mark_queue_item(item["id"], "hata", error=str(e))


def start_scheduler():
    """Günlük yükleme zamanlayıcısını başlatır."""
    tz = pytz.timezone(UPLOAD_TIMEZONE)
    h, m = map(int, UPLOAD_TIME.split(":"))

    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        do_scheduled_upload,
        CronTrigger(hour=h, minute=m, timezone=tz),
        id="daily_upload",
        name="Günlük Video Yükleme",
        misfire_grace_time=3600
    )

    log.info(f"Zamanlayıcı başladı — her gün {UPLOAD_TIME} {UPLOAD_TIMEZONE}")
    log.info(f"Yerel IP: {get_local_ip()}")
    log.info(f"Şirket ağı: {'EVET' if is_company_network() else 'HAYIR'}")
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    log.info("Upload Scheduler başlatılıyor...")
    scheduler = start_scheduler()
    log.info("Çalışıyor. Durdurmak için Ctrl+C")
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("Zamanlayıcı durduruldu.")
