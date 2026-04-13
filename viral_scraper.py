"""
Viral Kanal İçerik Çekici v3
- Twitter API v2 ile @tirajnews tweet'lerini çeker
- Nitter mirror'lar fallback olarak kalır
- yt-dlp ile tweet videolarını indirir
"""

import os, json, re, requests, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

TARGET_USER  = "tirajnews"
SEEN_FILE    = "data/viral_seen.json"
QUEUE_FILE   = "data/viral_queue.json"
OUTPUT_DIR   = Path("output/viral")
DAYS_BACK    = 3

from platform_helper import YTDLP_PATH

NITTER_MIRRORS = [
    "https://nitter.poast.org",
    "https://nitter.net",
    "https://nitter.catsarch.com",
    "https://nitter.moomoo.me",
]

RSSHUB_MIRRORS = [
    "https://rsshub.app/twitter/user/tirajnews",
    "https://rsshub.rss.pub/twitter/user/tirajnews",
]


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
    made = set()
    if not OUTPUT_DIR.exists(): return made
    for jf in OUTPUT_DIR.glob("*.json"):
        try:
            with open(jf,"r",encoding="utf-8") as f:
                tid = json.load(f).get("tweet_id","")
                if tid: made.add(tid)
        except: pass
    return made


def fetch_via_twitter_api() -> list:
    """Twitter API v2 ile tweet çeker."""
    try:
        bearer = os.environ.get("TWITTER_BEARER_TOKEN","")
        if not bearer:
            try:
                from config import TWITTER_BEARER_TOKEN
                bearer = TWITTER_BEARER_TOKEN
            except: pass
        if not bearer:
            return []

        # Kullanıcı ID'sini al
        user_url = f"https://api.twitter.com/2/users/by/username/{TARGET_USER}"
        headers  = {"Authorization": f"Bearer {bearer}"}
        r = requests.get(user_url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"  ⚠ Twitter API kullanıcı hatası: {r.status_code}")
            return []
        user_id = r.json()["data"]["id"]

        # Son tweet'leri çek
        cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
        tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
        params = {
            "max_results": 20,
            "tweet.fields": "created_at,public_metrics,attachments",
            "expansions": "attachments.media_keys",
            "media.fields": "type,url,preview_image_url",
            "start_time": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        r2 = requests.get(tweets_url, headers=headers, params=params, timeout=10)
        if r2.status_code != 200:
            print(f"  ⚠ Twitter API tweet hatası: {r2.status_code} {r2.text[:100]}")
            return []

        data   = r2.json()
        tweets = data.get("data", [])
        media  = {m["media_key"]: m for m in data.get("includes",{}).get("media",[])}

        results = []
        for t in tweets:
            tid     = t["id"]
            text    = t["text"]
            text    = re.sub(r'https?://\S+', '', text).strip()
            metrics = t.get("public_metrics", {})

            # Medya var mı?
            has_video = False
            img_url   = None
            for mk in t.get("attachments",{}).get("media_keys",[]):
                m = media.get(mk,{})
                if m.get("type") == "video":
                    has_video = True
                elif m.get("type") == "photo":
                    img_url = m.get("url") or m.get("preview_image_url")

            results.append({
                "id":        tid,
                "text":      text[:500],
                "link":      f"https://x.com/{TARGET_USER}/status/{tid}",
                "img_url":   img_url,
                "has_video": has_video,
                "pubdate":   t.get("created_at",""),
                "source":    f"@{TARGET_USER}",
                "likes":     metrics.get("like_count", 0),
                "retweets":  metrics.get("retweet_count", 0),
            })

        print(f"  ✅ Twitter API: {len(results)} tweet")
        return results
    except Exception as e:
        print(f"  ⚠ Twitter API hata: {e}")
        return []


def fetch_via_nitter() -> list:
    """Nitter mirror'lardan RSS çeker."""
    ns     = {"media": "http://search.yahoo.com/mrss/"}
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)

    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{TARGET_USER}/rss"
        try:
            r = requests.get(url, timeout=10, verify=False,
                            headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code != 200: continue
            root  = ET.fromstring(r.content)
            items = root.findall(".//item")
            if not items: continue

            print(f"  ✅ Nitter: {mirror}")
            tweets = []
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
                img_url   = None
                has_video = False
                for mc in item.findall("media:content", ns):
                    if "image" in mc.get("type",""): img_url = mc.get("url","")
                    if "video" in mc.get("type",""): has_video = True
                tweets.append({
                    "id": tid, "text": text[:500],
                    "link": f"https://x.com/{TARGET_USER}/status/{tid}",
                    "img_url": img_url, "has_video": has_video,
                    "pubdate": pubdate, "source": f"@{TARGET_USER}",
                    "likes": 0, "retweets": 0,
                })
            return tweets
        except Exception as e:
            print(f"  ⚠ {mirror}: {e}")
            continue

    # RSSHub fallback
    for rsshub_url in RSSHUB_MIRRORS:
        try:
            r = requests.get(rsshub_url, timeout=10, verify=False,
                            headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code != 200: continue
            root  = ET.fromstring(r.content)
            items = root.findall(".//item")
            if not items: continue
            print(f"  ✅ RSSHub: {rsshub_url}")
            tweets = []
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
                tweets.append({
                    "id": tid, "text": text[:500],
                    "link": f"https://x.com/{TARGET_USER}/status/{tid}",
                    "img_url": None, "has_video": False,
                    "pubdate": pubdate, "source": f"@{TARGET_USER}",
                    "likes": 0, "retweets": 0,
                })
            return tweets
        except: continue

    return []


def fetch_tweets() -> list:
    """Önce Twitter API, olmadı Nitter dener."""
    # 1. Twitter API v2
    tweets = fetch_via_twitter_api()
    if tweets:
        return tweets
    # 2. Nitter / RSSHub
    print(f"  → Twitter API başarısız, Nitter deneniyor...")
    tweets = fetch_via_nitter()
    return tweets


def download_video_ytdlp(tweet_url: str, output_path: str) -> bool:
    try:
        cmd = [YTDLP_PATH, "--no-check-certificate", "-f", "mp4/best[ext=mp4]/best",
               "--no-playlist", "-o", output_path, "--quiet", "--no-warnings", tweet_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            return True
    except Exception as e:
        print(f"  ⚠ yt-dlp hata: {e}")
    return False


def check_new_tweets(force: bool = False) -> list:
    print(f"  🔍 @{TARGET_USER} kontrol ediliyor...")
    seen     = set() if force else load_seen()
    made     = get_made_tweet_ids()
    skip_ids = seen | made
    tweets   = fetch_tweets()
    new      = []
    for tweet in tweets:
        tid = tweet["id"]
        if tid in skip_ids: continue
        seen.add(tid)
        new.append(tweet)
    if not force:
        save_seen(seen)
    print(f"  → {len(new)} yeni tweet")
    return new


def add_to_viral_queue(tweets: list) -> int:
    made  = get_made_tweet_ids()
    queue = load_queue()
    queue = [q for q in queue
             if q.get("tweet_id") not in made and q.get("status") != "yuklendi"]
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
    print(f"  ✅ {added} eklendi (toplam: {len(queue)})")
    return added


if __name__ == "__main__":
    new = check_new_tweets()
    if new:
        add_to_viral_queue(new)
        for t in new[:3]:
            print(f"  📝 {t['text'][:60]}")
    else:
        print("Yeni tweet yok")
