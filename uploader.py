"""
Modül 4: YouTube'a Video Yükleme
OAuth2 kimlik doğrulama ve YouTube Data API v3 ile otomatik yükleme.
"""

import os
import json
import pickle
from pathlib import Path
from datetime import datetime, timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from config import (
    OAUTH_CREDENTIALS_FILE, OAUTH_TOKEN_FILE,
    VIDEO_PRIVACY, VIDEO_CATEGORY_ID
)

# YouTube API erişim kapsamları
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]


def _load_creds_from_env(channel: str, token_file: str):
    """Env variable'dan token yukle ve yenile."""
    from google.oauth2.credentials import Credentials as _GC
    import base64 as _b64
    env_key = "TOKEN_SOZLER" if channel == "sozler" else f"TOKEN_{channel.upper()}"
    val = os.environ.get(env_key, "")
    if not val:
        return None
    try:
        decoded = _b64.b64decode(val).decode("utf-8")
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(decoded)
        creds = _GC.from_authorized_user_file(token_file)
        if creds and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_file, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                print(f"  ✅ Token env'den yuklendi+yenilendi: {token_file}")
            except Exception as re:
                print(f"  ⚠ Refresh basarisiz: {re} — token'i oldugu gibi kullaniyor")
        return creds
    except Exception as e:
        print(f"  ⚠ Env token yuklenemedi: {e}")
        return None


def get_authenticated_service(channel: str = "sozler"):
    """OAuth2 ile YouTube API istemcisi — kanal bazli token."""
    from google.oauth2.credentials import Credentials as GCreds

    token_file = OAUTH_TOKEN_FILE if channel == "sozler" else f"token_{channel}.json"
    creds_file = OAUTH_CREDENTIALS_FILE if channel in ("sozler","notesofhistory") else f"credentials_{channel}.json"

    credentials = None

    # 1. Disk'teki token'i yukle
    if os.path.exists(token_file):
        try:
            credentials = GCreds.from_authorized_user_file(token_file)
            print(f"  → Token yuklendi: {token_file} | valid={credentials.valid} expired={credentials.expired}")
        except Exception as e:
            print(f"  ⚠ Token yuklenemedi: {e}")

    # 2. Suresi dolmussa yenile
    if credentials and not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                with open(token_file, "w", encoding="utf-8") as f:
                    f.write(credentials.to_json())
                print(f"  ✅ Token yenilendi: {token_file}")
            except Exception as e:
                print(f"  ⚠ Token yenileme basarisiz: {e}")
                credentials = None
        else:
            credentials = None

    # 3. Hala gecersizse env variable'dan yeniden yukle
    if not credentials or not credentials.valid:
        print(f"  → Env variable'dan token yukleniyor: TOKEN_{channel.upper()}")
        credentials = _load_creds_from_env(channel, token_file)

    # 4. Sozler icin pickle fallback
    if not credentials and channel == "sozler":
        try:
            with open(OAUTH_TOKEN_FILE, "rb") as f:
                credentials = pickle.load(f)
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
        except: pass

    if not credentials or not credentials.valid:
        raise Exception(
            f"Token gecersiz: {token_file}. "
            f"Bilgisayarda 'python create_{channel}_token.py' calistir, "
            f"Railway'de TOKEN_{channel.upper()} guncelle."
        )

    return build("youtube", "v3", credentials=credentials)


def build_video_metadata(content_plan: dict, scheduled_time: str = None) -> dict:
    """
    YouTube yükleme için snippet ve status metadata'sını hazırlar.
    scheduled_time: ISO 8601 format, ör. "2024-01-15T18:00:00+03:00"
    """
    # Başlık max 100 karakter
    title = content_plan["title"][:100]

    # Açıklama: içerik + hashtag
    hashtags = " ".join(content_plan.get("hashtags", [])[:8])
    us_hashtags = " ".join(content_plan.get("us_trending_hashtags", [])[:5])
    desc_base = content_plan.get("description", "")
    if us_hashtags:
        description = f"{desc_base}\n\n{hashtags} {us_hashtags}"[:5000]
    else:
        description = f"{desc_base}\n\n{hashtags}"[:5000]

    # Tags max 500 karakter toplam
    tags = content_plan.get("tags", [])[:MAX_TAGS_UPLOAD]

    snippet = {
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": VIDEO_CATEGORY_ID,
        "defaultLanguage": "tr",
        "defaultAudioLanguage": "tr"
    }

    status = {
        "privacyStatus": VIDEO_PRIVACY,
        "selfDeclaredMadeForKids": False
    }

    # Zamanlanmış yükleme (private → scheduled)
    if scheduled_time and VIDEO_PRIVACY == "public":
        status["privacyStatus"] = "private"
        status["publishAt"] = scheduled_time

    return {"snippet": snippet, "status": status}


MAX_TAGS_UPLOAD = 15


def upload_video(youtube, video_path: str, content_plan: dict, scheduled_time: str = None, channel_id: str = None) -> dict:
    """
    Videoyu YouTube'a yükler.
    Returns: upload response (video_id, title, url)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"  → Yükleniyor: {video_path} ({file_size_mb:.1f} MB)")

    metadata = build_video_metadata(content_plan, scheduled_time)

    body = {
        "snippet": metadata["snippet"],
        "status": metadata["status"]
    }

    # Hedef kanal ID'si (birden fazla kanal varsa)
    if channel_id:
        body["snippet"]["channelId"] = channel_id

    # Yükleme isteği
    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 10   # 10MB chunk
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    # Resumable yükleme (büyük dosyalar için güvenli)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            print(f"  → Yükleme: %{progress}", end="\r")

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    print(f"\n  ✅ Video yüklendi!")
    print(f"     ID: {video_id}")
    print(f"     URL: {video_url}")
    if scheduled_time:
        print(f"     Yayın zamanı: {scheduled_time}")

    return {
        "video_id": video_id,
        "title": response["snippet"]["title"],
        "url": video_url,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "scheduled_for": scheduled_time
    }


def add_to_playlist(youtube, video_id: str, playlist_id: str):
    """Yüklenen videoyu bir playlist'e ekler."""
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    ).execute()
    print(f"  → Playlist'e eklendi: {playlist_id}")


def run_upload(content_plan: dict, video_path: str, scheduled_time: str = None, channel_id: str = None, channel: str = "sozler") -> dict:
    """Tam yükleme pipeline'ını çalıştırır."""
    print("📤 YouTube yükleme başlatılıyor...")

    youtube = get_authenticated_service(channel)
    result = upload_video(youtube, video_path, content_plan, scheduled_time)

    # Upload kaydını sakla
    upload_log_path = "upload_history.json"
    history = []
    if os.path.exists(upload_log_path):
        with open(upload_log_path, "r", encoding="utf-8") as f:
            history = json.load(f)

    history.append({**result, "content_plan": content_plan})

    with open(upload_log_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"✅ Yükleme tamamlandı: {result['url']}")
    return result


if __name__ == "__main__":
    with open("content_plan.json", "r", encoding="utf-8") as f:
        plan = json.load(f)

    # Bugün 18:00'e zamanla
    today = datetime.now()
    scheduled = today.replace(hour=18, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S+03:00")

    result = run_upload(plan, "output/video.mp4", scheduled_time=scheduled)
    print(f"\n🎉 Video yayında: {result['url']}")
