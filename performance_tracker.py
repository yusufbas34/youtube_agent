"""
Modül 5: Performans Takibi
Yüklenen videoların görüntülenme, CTR, izlenme süresi ve abone verilerini takip eder.
Sonuçları öğrenme döngüsüne (trend_analyzer) besler.
"""

import json
import os
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import pickle
import anthropic

from config import ANTHROPIC_API_KEY
from uploader import get_authenticated_service


def get_channel_analytics(youtube_analytics, channel_id: str, days: int = 7) -> dict:
    """Son N günün kanal analitiğini çeker (YouTube Analytics API gerektirir)."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = youtube_analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start_date,
        endDate=end_date,
        metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost,likes,comments,shares,annotationClickThroughRate",
        dimensions="video",
        sort="-views",
        maxResults=20
    ).execute()

    return response


def get_video_stats_basic(youtube, video_ids: list) -> dict:
    """YouTube Data API ile temel video istatistiklerini çeker (Analytics API gerekmez)."""
    stats = {}
    # Max 50 video per request
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        response = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(batch)
        ).execute()

        for item in response.get("items", []):
            s = item.get("statistics", {})
            stats[item["id"]] = {
                "title": item["snippet"]["title"],
                "published_at": item["snippet"]["publishedAt"],
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
                "favorites": int(s.get("favoriteCount", 0))
            }
    return stats


def load_upload_history() -> list:
    """Yüklenen videoların geçmişini okur."""
    if not os.path.exists("upload_history.json"):
        return []
    with open("upload_history.json", "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_performance_with_ai(videos_stats: dict, history: list) -> dict:
    """Claude ile performans verilerini analiz eder, öğrenilenleri çıkarır."""
    import ssl, httpx
    http_client = httpx.Client(verify=False)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http_client)

    # Önceki video performansını hazırla
    performance_data = []
    for video_id, stats in videos_stats.items():
        # Upload history'den içerik bilgilerini bul
        content_info = next(
            (h["content_plan"] for h in history if h.get("video_id") == video_id),
            {}
        )
        performance_data.append({
            "video_id": video_id,
            "title": stats["title"],
            "views": stats["views"],
            "likes": stats["likes"],
            "comments": stats["comments"],
            "engagement_rate": round((stats["likes"] + stats["comments"]) / max(stats["views"], 1) * 100, 2),
            "tags_used": content_info.get("tags", [])[:5],
            "thumbnail_text": content_info.get("thumbnail_text", ""),
            "topic": content_info.get("topic", "")
        })

    # Yüksek performanslı olanları sırala
    performance_data.sort(key=lambda x: x["views"], reverse=True)

    prompt = f"""
Sen bir YouTube analytics uzmanısın.

Aşağıdaki video performans verilerini analiz et:
{json.dumps(performance_data[:10], ensure_ascii=False, indent=2)}

Lütfen şunları çıkar:
1. En iyi performans gösteren 3 video ve neden iyi performans gösterdiği
2. En kötü performans gösteren 2 video ve olası sebepler
3. Başlık/thumbnail kalıpları: hangi tip başlıklar daha fazla tıklanıyor?
4. Gelecek videolar için 5 somut öneri
5. Genel kanal büyüme trendi (yükselen/durgun/düşen)

JSON formatında yanıt ver:
{{
  "top_performers": [{{"video_id": "...", "title": "...", "reason": "..."}}],
  "underperformers": [{{"video_id": "...", "title": "...", "issue": "..."}}],
  "title_patterns": {{"what_works": "...", "what_doesnt": "..."}},
  "recommendations": ["öneri1", "öneri2", ...],
  "channel_trend": "rising|stable|declining",
  "trend_note": "..."
}}
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    return json.loads(response_text.strip())


def run_performance_tracking() -> dict:
    """Tam performans takibi pipeline'ını çalıştırır."""
    print("📈 Performans takibi başlatılıyor...")

    history = load_upload_history()
    if not history:
        print("  → Henüz yüklenen video yok.")
        return {}

    youtube = get_authenticated_service()
    video_ids = [h["video_id"] for h in history if "video_id" in h]

    if not video_ids:
        print("  → Video ID bulunamadı.")
        return {}

    print(f"  → {len(video_ids)} video için istatistik çekiliyor...")
    stats = get_video_stats_basic(youtube, video_ids)

    print("  → AI ile performans analizi yapılıyor...")
    analysis = analyze_performance_with_ai(stats, history)

    result = {
        "tracked_at": datetime.now().isoformat(),
        "video_count": len(stats),
        "total_views": sum(s["views"] for s in stats.values()),
        "total_likes": sum(s["likes"] for s in stats.values()),
        "video_stats": stats,
        "analysis": analysis
    }

    with open("performance_report.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    trend_emoji = {"rising": "📈", "stable": "➡️", "declining": "📉"}.get(
        analysis.get("channel_trend", "stable"), "➡️"
    )

    print(f"\n✅ Performans raporu hazır:")
    print(f"   Toplam görüntülenme: {result['total_views']:,}")
    print(f"   Kanal trendi: {trend_emoji} {analysis.get('channel_trend', 'stable')}")
    print(f"   Öneri sayısı: {len(analysis.get('recommendations', []))}")

    return result


if __name__ == "__main__":
    report = run_performance_tracking()
    if report:
        print("\n💡 Öneriler:")
        for i, rec in enumerate(report["analysis"].get("recommendations", []), 1):
            print(f"  {i}. {rec}")
