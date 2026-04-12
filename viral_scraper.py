"""
Viral Kanal İçerik Çekici
- nitter.net RSS ile @tirajnews tweet'lerini çeker (son 3 gün)
- yt-dlp ile tweet videolarını indirir
- Video yapılanları atlar, yenileri kuyruğa ekler
"""

import os, json, re, requests, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

NITTER_MIRRORS = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
]
NITTER_BASE  = "https://nitter.net"
TARGET_USER  = "tirajnews"
SEEN_FILE    = "data/viral_seen.json"
QUEUE_FILE   = "data/viral_queue.json"
OUTPUT_DIR   = Path("output/viral")
YTDLP_PATH   = r"C:\Users\yusuf.bas\youtube_agent\yt-dlp.exe"
DAYS_BACK    = 3


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE,"r",encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list): return set(data)
                return set(data.get("ids",[]))
        except: pass
    return set()


def save_seen(seen: set):
    os.makedirs("data", exist_ok=True)
    with open(SEEN_FILE,"w",encoding="utf-8") as f:
        json.dump({"ids":list(seen),"updated":datetime.now().isoformat()}, f, indent=2)


def load_queue() -> list:
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return []


def save_queue(q: list):
    os.makedirs("data", exist_ok=True)
    with open(QUEUE_FILE,"w",encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)


def get_made_tweet_ids() -> set:
    """Video yapılmış tweet ID'lerini döner."""
    made = set()
    if not OUTPUT_DIR.exists(): return made
    for jf in OUTPUT_DIR.glob("*.json"):
        try:
            with open(jf,"r",encoding="utf-8") as f:
                tid = json.load(f).get("tweet_id","")
                if tid: made.add(tid)
        except: pass
    return made


def download_video_ytdlp(tweet_url: str, output_path: str) -> bool:
    """yt-dlp ile tweet videosunu indirir."""
    try:
        cmd = [
            YTDLP_PATH,
            "--no-check-certificate",
            "-f", "mp4/best[ext=mp4]/best",
            "--no-playlist",
            "-o", output_path,
            "--quiet",
            tweet_url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            if size > 10000:
                print(f"  ✅ Video indirildi ({size//1024}KB)")
                return True
        else:
            if result.stderr:
                print(f"  ⚠ yt-dlp: {result.stderr[:100]}")
    except Exception as e:
        print(f"  ⚠ yt-dlp hata: {e}")
    return False


def fetch_tweets() -> list:
    """nitter.net RSS'ten son 3 günün tweetlerini çeker. Birden fazla mirror dener."""
    tweets  = []
    cutoff  = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    ns      = {"media": "http://search.yahoo.com/mrss/"}

    last_error = None
    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{TARGET_USER}/rss"
        try:
            r = requests.get(url, timeout=15, verify=False,
                            headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code != 200:
                print(f"  ⚠ {mirror} → HTTP {r.status_code}")
                continue

            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            if not items:
                print(f"  ⚠ {mirror} → Boş feed")
                continue

            print(f"  ✅ Mirror çalışıyor: {mirror}")
            for item in items:
                link    = item.findtext("link","")
                desc    = item.findtext("description","")
                title   = item.findtext("title","")
                pubdate = item.findtext("pubDate","")

                try:
                    pub_dt = parsedate_to_datetime(pubdate)
                    if pub_dt < cutoff: continue
                except: pass

                tid = link.rstrip("/").split("/")[-1].split("#")[0] if link else ""
                if not tid: continue

                text = re.sub(r'<[^>]+>', '', desc or title).strip()
                text = re.sub(r'https?://\S+', '', text).strip()
                text = re.sub(r'\s+', ' ', text).strip()
                if not text: text = title

                img_url = None
                for mc in item.findall("media:content", ns):
                    if "image" in mc.get("type",""):
                        img_url = mc.get("url","")
                        break

                # Tweet'te video var mı? (media:content type=video veya URL pattern)
                has_video = any(
                    "video" in mc.get("type","") 
                    for mc in item.findall("media:content", ns)
                )

                # Retweet / beğeni sayısı RSS description'dan çıkar
                rt_match  = re.search(r'(\d[\d,]*)\s*(?:RT|retweet)', desc or '', re.IGNORECASE)
                fav_match = re.search(r'(\d[\d,]*)\s*(?:like|beğeni|fav)', desc or '', re.IGNORECASE)
                retweets  = int((rt_match.group(1) if rt_match else '0').replace(',',''))
                likes     = int((fav_match.group(1) if fav_match else '0').replace(',',''))

                tweets.append({
                    "id":        tid,
                    "text":      text[:500],
                    "link":      f"https://x.com/{TARGET_USER}/status/{tid}",
                    "img_url":   img_url,
                    "has_video": has_video,
                    "pubdate":   pubdate,
                    "source":    f"@{TARGET_USER}",
                    "retweets":  retweets,
                    "likes":     likes,
                })

            print(f"  → {len(tweets)} tweet alındı (son {DAYS_BACK} gün)")
            return tweets

        except Exception as e:
            last_error = e
            print(f"  ⚠ {mirror} hata: {e}")
            continue

    print(f"  ❌ Tüm mirror'lar başarısız. Son hata: {last_error}")
    return []


def check_new_tweets(force: bool = False) -> list:
    """Yeni tweet'leri kontrol eder. force=True ise seen cache'i atlar."""
    print(f"  🔍 @{TARGET_USER} kontrol ediliyor...")
    seen     = set() if force else load_seen()
    made     = get_made_tweet_ids()
    skip_ids = seen | made

    tweets = fetch_tweets()
    new    = []

    for tweet in tweets:
        tid = tweet["id"]
        if tid in skip_ids: continue
        seen.add(tid)
        new.append(tweet)

    if not force:
        save_seen(seen)
    print(f"  → {len(new)} yeni tweet ({'zorla' if force else 'normal'})")
    return new


def add_to_viral_queue(tweets: list) -> int:
    """Tweet'leri kuyruğa ekler, video yapılanları temizler."""
    made  = get_made_tweet_ids()
    queue = load_queue()
    # Video yapılanları kuyruktan sil
    queue = [q for q in queue
             if q.get("tweet_id") not in made
             and q.get("status") != "yuklendi"]

    existing = {q.get("tweet_id") for q in queue}
    added = 0

    for tweet in tweets:
        if tweet["id"] in existing: continue
        queue.append({
            "id":        f"vq_{tweet['id']}",
            "tweet_id":  tweet["id"],
            "text":      tweet["text"],
            "link":      tweet["link"],
            "img_url":   tweet.get("img_url"),
            "has_video": tweet.get("has_video", False),
            "source":    tweet["source"],
            "pubdate":   tweet.get("pubdate",""),
            "likes":     tweet.get("likes", 0),
            "retweets":  tweet.get("retweets", 0),
            "status":    "bekliyor",
            "added_at":  datetime.now().isoformat(),
            "video_path": None,
        })
        added += 1

    save_queue(queue)
    print(f"  ✅ {added} eklendi (toplam kuyruk: {len(queue)})")
    return added


if __name__ == "__main__":
    new = check_new_tweets()
    if new:
        add_to_viral_queue(new)
        for t in new[:3]:
            print(f"  📝 {t['text'][:60]}")
    else:
        print("Yeni tweet yok")
