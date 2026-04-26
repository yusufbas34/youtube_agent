"""
Viral Kanal İçerik Üreticisi v4
- Twitter API / Nitter erişilemiyorsa Claude ile viral konu üretir
- yt-dlp ile ilgili video arar
"""

import os, json, re, requests, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

TARGET_USER = "tirajnews"
SEEN_FILE   = "data/viral_seen.json"
QUEUE_FILE  = "data/viral_queue.json"
OUTPUT_DIR  = Path("output/viral")
DAYS_BACK   = 3

from platform_helper import YTDLP_PATH

NITTER_MIRRORS = [
    "https://nitter.poast.org",
    "https://nitter.net",
    "https://nitter.catsarch.com",
    "https://nitter.privacydev.net",
    "https://nitter.kavin.rocks",
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

        user_url = f"https://api.twitter.com/2/users/by/username/{TARGET_USER}"
        headers  = {"Authorization": f"Bearer {bearer}"}
        r = requests.get(user_url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"  ⚠ Twitter API: {r.status_code}")
            return []
        user_id = r.json()["data"]["id"]

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
            return []

        data   = r2.json()
        tweets = data.get("data", [])
        media  = {m["media_key"]: m for m in data.get("includes",{}).get("media",[])}

        results = []
        for t in tweets:
            tid     = t["id"]
            text    = re.sub(r'https?://\S+', '', t["text"]).strip()
            metrics = t.get("public_metrics", {})
            has_video = any(
                media.get(mk,{}).get("type") == "video"
                for mk in t.get("attachments",{}).get("media_keys",[])
            )
            results.append({
                "id": tid, "text": text[:500],
                "link": f"https://x.com/{TARGET_USER}/status/{tid}",
                "img_url": None, "has_video": has_video,
                "pubdate": t.get("created_at",""),
                "source": f"@{TARGET_USER}",
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
            })
        print(f"  ✅ Twitter API: {len(results)} tweet")
        return results
    except Exception as e:
        print(f"  ⚠ Twitter API hata: {e}")
        return []


def fetch_via_nitter() -> list:
    """Nitter mirror'lardan RSS çeker."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    ns = {"media": "http://search.yahoo.com/mrss/"}
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)

    for mirror in NITTER_MIRRORS:
        url = f"{mirror}/{TARGET_USER}/rss"
        try:
            r = requests.get(url, timeout=8, verify=False,
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
                tweets.append({
                    "id": tid, "text": text[:500],
                    "link": f"https://x.com/{TARGET_USER}/status/{tid}",
                    "img_url": None, "has_video": False,
                    "pubdate": pubdate, "source": f"@{TARGET_USER}",
                    "likes": 0, "retweets": 0,
                })
            return tweets
        except Exception as e:
            print(f"  ⚠ {mirror}: {e}")
            continue
    return []


def generate_viral_topics_with_claude() -> list:
    """Twitter erişimi yoksa Claude ile güncel viral konular üretir."""
    try:
        import httpx, anthropic
        from config import ANTHROPIC_API_KEY
        http   = httpx.Client(verify=False)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)

        today = datetime.now().strftime("%d %B %Y")
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role":"user","content":f"""
Bugün {today}. Türkiye'de son günlerde viral olan veya güncel olan 5 ilginç konu üret.
Bunlar sosyal medyada paylaşılan, şaşırtıcı veya ilginç videolara konu olabilecek şeyler olsun.
Spor, doğa olayları, ilginç insanlar, komik/şaşırtıcı olaylar olabilir.

Sadece JSON döndür:
[
  {{"id": "ai_001", "text": "konu açıklaması (max 100 karakter)", "search_query": "youtube arama terimi ingilizce"}},
  ...
]
"""}]
        )
        text = msg.content[0].text.strip()
        if "```json" in text: text = text.split("```json")[1].split("```")[0]
        elif "```" in text:   text = text.split("```")[1].split("```")[0]
        topics = json.loads(text.strip())

        results = []
        ts = datetime.now().strftime("%Y%m%d%H%M")
        for i, t in enumerate(topics[:5]):
            results.append({
                "id":         t.get("id", f"ai_{ts}_{i}"),
                "text":       t.get("text",""),
                "link":       "",
                "img_url":    None,
                "has_video":  False,
                "pubdate":    datetime.now().isoformat(),
                "source":     "AI Generated",
                "likes":      0,
                "retweets":   0,
                "search_query": t.get("search_query",""),
            })
        print(f"  ✅ Claude viral konular: {len(results)} konu")
        return results
    except Exception as e:
        print(f"  ⚠ Claude viral üretim hata: {e}")
        return []


def fetch_tweets() -> list:
    """Önce Twitter API, sonra Nitter, son çare Claude."""
    # 1. Twitter API
    tweets = fetch_via_twitter_api()
    if tweets:
        return tweets
    # 2. Nitter
    print("  → Nitter deneniyor...")
    tweets = fetch_via_nitter()
    if tweets:
        return tweets
    # 3. Claude ile üret
    print("  → Twitter/Nitter erişilemedi, Claude ile viral konular üretiliyor...")
    return generate_viral_topics_with_claude()


def check_new_tweets(force: bool = False) -> list:
    print(f"  🔍 Viral içerik kontrol ediliyor...")
    made       = get_made_tweet_ids()
    queue      = load_queue()
    queued_ids = {q.get("tweet_id") for q in queue if q.get("status") not in ("yuklendi",)}
    skip_ids   = made | queued_ids
    tweets     = fetch_tweets()
    new        = [t for t in tweets if t["id"] not in skip_ids]
    print(f"  → {len(new)} yeni içerik")
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
            "id":           f"vq_{tweet['id']}",
            "tweet_id":     tweet["id"],
            "text":         tweet["text"],
            "link":         tweet.get("link",""),
            "img_url":      tweet.get("img_url"),
            "has_video":    tweet.get("has_video", False),
            "source":       tweet.get("source",""),
            "pubdate":      tweet.get("pubdate",""),
            "likes":        tweet.get("likes", 0),
            "retweets":     tweet.get("retweets", 0),
            "search_query": tweet.get("search_query",""),
            "status":       "bekliyor",
            "added_at":     datetime.now().isoformat(),
            "video_path":   None,
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
        print("Yeni içerik yok")
