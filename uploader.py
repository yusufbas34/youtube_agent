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


def get_authenticated_service(channel: str = "sozler"):
    """OAuth2 ile YouTube API istemcisi oluşturur."""
    credentials = None

    # Kanal bazlı token dosyası
    token_file = f"token_{channel}.json" if channel != "sozler" else OAUTH_TOKEN_FILE
    # notesofhistory ayrı credentials yok, ana credentials.json kullan
    if channel in ("sozler", "notesofhistory"):
        creds_file = OAUTH_CREDENTIALS_FILE
    else:
        creds_file = f"credentials_{channel}.json"

    # Kayıtlı token varsa yükle
    if os.path.exists(token_file):
        try:
            from google.oauth2.credentials import Credentials
            credentials = Credentials.from_authorized_user_file(token_file)
        except:
            pass

    if not credentials and os.path.exists(OAUTH_TOKEN_FILE):
        with open(OAUTH_TOKEN_FILE, "rb") as f:
            credentials = pickle.load(f)

    # Token geçersizse veya yoksa yenile / al
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("  → Token yenileniyor...")
            credentials.refresh(Request())
        else:
            print("  → Tarayıcıda YouTube izni gerekiyor...")
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_file, SCOPES
            )
            credentials = flow.run_local_server(port=0)

        with open(OAUTH_TOKEN_FILE, "wb") as f:
            pickle.dump(credentials, f)
        print("  ✅ Token kaydedildi.")

    return build("youtube", "v3", credentials=credentials)


def build_video_metadata(content_plan: dict, scheduled_time: str = None) -> dict:
    """
    YouTube yükleme için snippet ve status metadata'sını hazırlar.
    scheduled_time: ISO 8601 format, ör. "2024-01-15T18:00:00+03:00"
    """
    # Başlık max 100 karakter
    title = content_plan["title"][:100]

    # Açıklama: içerik + hashtag
    hashtags = " ".join(content_plan.get("hashtags", [])[:5])
    description = f"{content_plan['description']}\n\n{hashtags}"[:5000]

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
