"""
Modül 1: YouTube Trend Analizi
YouTube Data API v3 kullanarak trending konuları, rakip analizi ve SEO fırsatlarını bulur.
"""

import os
import json
from datetime import datetime, timedelta
from googleapiclient.discovery import build
import anthropic

from config import (
    YOUTUBE_API_KEY, ANTHROPIC_API_KEY,
    CHANNEL_NICHE, CHANNEL_LANGUAGE, TARGET_AUDIENCE
)


def get_youtube_client():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def fetch_trending_videos(youtube, region_code="TR", max_results=20):
    """Türkiye'deki trend videoları çeker."""
    request = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        chart="mostPopular",
        regionCode=region_code,
        maxResults=max_results,
        videoCategoryId="28"   # Science & Technology
    )
    response = request.execute()

    trending = []
    for item in response.get("items", []):
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        trending.append({
            "video_id": item["id"],
            "title": snippet["title"],
            "channel": snippet["channelTitle"],
            "description": snippet["description"][:200],
            "published_at": snippet["publishedAt"],
            "tags": snippet.get("tags", [])[:10],
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "duration": item["contentDetails"]["duration"]
        })

    trending.sort(key=lambda x: x["view_count"], reverse=True)
    return trending


def search_niche_videos(youtube, query, max_results=15):
    """Niş konuda son 7 günün popüler videolarını arar."""
    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    request = youtube.search().list(
        part="snippet",
        q=query,
        type="video",
        order="viewCount",
        publishedAfter=seven_days_ago,
        relevanceLanguage=CHANNEL_LANGUAGE,
        regionCode="TR",
        maxResults=max_results,
        videoDuration="short" if "shorts" in query.lower() else "any"
    )
    response = request.execute()

    videos = []
    for item in response.get("items", []):
        videos.append({
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "description": item["snippet"]["description"][:150],
            "published_at": item["snippet"]["publishedAt"]
        })
    return videos


def get_video_statistics(youtube, video_ids):
    """Verilen video ID listesi için istatistik çeker."""
    ids_str = ",".join(video_ids[:50])
    request = youtube.videos().list(
        part="statistics",
        id=ids_str
    )
    response = request.execute()

    stats = {}
    for item in response.get("items", []):
        s = item.get("statistics", {})
        stats[item["id"]] = {
            "views": int(s.get("viewCount", 0)),
            "likes": int(s.get("likeCount", 0)),
            "comments": int(s.get("commentCount", 0))
        }
    return stats


def analyze_trends_with_ai(trending_videos, niche_videos):
    """Claude ile trend verilerini analiz eder, içerik fırsatlarını tespit eder."""
    import ssl, httpx
    http_client = httpx.Client(verify=False)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http_client)

    trend_summary = json.dumps({
        "trending_top5": trending_videos[:5],
        "niche_top10": niche_videos[:10]
    }, ensure_ascii=False, indent=2)

    prompt = f"""
Sen bir YouTube içerik stratejisti ve SEO uzmanısın.

Kanal Nişi: {CHANNEL_NICHE}
Hedef Kitle: {TARGET_AUDIENCE}
İçerik Dili: Türkçe

Aşağıdaki YouTube trend verileri sana sunulmuştur:

{trend_summary}

Lütfen şunu üret:
1. En çok fırsat sunan 5 video konusu (başlık önerisiyle birlikte)
2. Her konu için neden trend olduğuna dair kısa analiz (1-2 cümle)
3. Genel trend paterni: hangi içerik formatları öne çıkıyor?
4. Bu haftanın en iyi video konusu (tek seçim, gerekçesiyle)

Yanıtını JSON formatında ver:
{{
  "opportunities": [
    {{"rank": 1, "topic": "...", "suggested_title": "...", "reason": "...", "estimated_views": "..."}}
  ],
  "trend_pattern": "...",
  "best_pick": {{"topic": "...", "title": "...", "reasoning": "..."}}
}}
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text
    # JSON bloğunu temizle
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    return json.loads(response_text.strip())


def run_trend_analysis():
    """Tam trend analizi pipeline'ını çalıştırır."""
    print("📊 Trend analizi başlatılıyor...")

    youtube = get_youtube_client()

    print("  → Türkiye trend videoları çekiliyor...")
    trending = fetch_trending_videos(youtube)

    print(f"  → '{CHANNEL_NICHE}' nişi aranıyor...")
    niche_videos = search_niche_videos(youtube, CHANNEL_NICHE)

    # İstatistikleri ekle
    if niche_videos:
        video_ids = [v["video_id"] for v in niche_videos]
        stats = get_video_statistics(youtube, video_ids)
        for v in niche_videos:
            v.update(stats.get(v["video_id"], {}))

    print("  → AI ile analiz yapılıyor...")
    analysis = analyze_trends_with_ai(trending, niche_videos)

    # Sonuçları kaydet
    result = {
        "analyzed_at": datetime.now().isoformat(),
        "trending_count": len(trending),
        "niche_count": len(niche_videos),
        "analysis": analysis
    }

    with open("trend_analysis.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ Analiz tamamlandı. En iyi pick: {analysis['best_pick']['title']}")
    return result


if __name__ == "__main__":
    result = run_trend_analysis()
    print("\n🎯 Fırsatlar:")
    for opp in result["analysis"]["opportunities"]:
        print(f"  {opp['rank']}. {opp['suggested_title']}")
    print(f"\n⭐ Haftanın seçimi: {result['analysis']['best_pick']['title']}")
