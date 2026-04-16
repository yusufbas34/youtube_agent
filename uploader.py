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


def _update_railway_token(channel: str, token_json: str):
    """Token yenilenince Railway environment variable'ını günceller."""
    try:
        import base64, requests
        railway_token = os.environ.get("RAILWAY_API_TOKEN","")
        service_id    = os.environ.get("RAILWAY_SERVICE_ID","")
        environment_id = os.environ.get("RAILWAY_ENVIRONMENT_ID","")
        if not railway_token or not service_id:
            return  # Railway değil veya API token yok

        env_key_map = {
            "sozler": "TOKEN_SOZLER",
            "tarih":  "TOKEN_TARIH",
            "viral":  "TOKEN_VIRAL",
        }
        env_key = env_key_map.get(channel)
        if not env_key:
            return

        b64_value = base64.b64encode(token_json.encode()).decode()

        # Railway GraphQL API
        query = """
        mutation UpsertVariables($input: VariableCollectionUpsertInput!) {
          variableCollectionUpsert(input: $input)
        }
        """
        variables = {
            "input": {
                "serviceId": service_id,
                "environmentId": environment_id,
                "variables": {env_key: b64_value}
            }
        }
        r = requests.post(
            "https://backboard.railway.app/graphql/v2",
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {railway_token}",
                     "Content-Type": "application/json"},
            timeout=10
        )
        if r.status_code == 200:
            print(f"  ✅ Railway {env_key} güncellendi")
        else:
            print(f"  ⚠ Railway API: {r.status_code}")
    except Exception as e:
        print(f"  ⚠ Railway token güncelleme başarısız: {e}")


def get_authenticated_service(channel: str = "sozler"):
    """OAuth2 ile YouTube API istemcisi oluşturur."""
    TOKEN_MAP = {
        "sozler": ("token.json",       "credentials.json"),
        "tarih":  ("token_tarih.json", "credentials_tarih.json.json"),
        "viral":  ("token_viral.json", "credentials_viral.json"),
    }
    token_file, creds_file = TOKEN_MAP.get(channel, TOKEN_MAP["sozler"])
    print(f"  → Kanal: {channel} | Token: {token_file}")

    credentials = None

    if os.path.exists(token_file):
        try:
            from google.oauth2.credentials import Credentials
            credentials = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception as e:
            print(f"  ⚠ Token okunamadı: {e}")
            credentials = None

    if not credentials:
        print(f"  → Token yok, yeni alınıyor ({channel})...")
    elif not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            print(f"  → Token süresi dolmuş, yenileniyor...")
            try:
                import requests as req_lib
                # Credentials dosyasından client_id ve client_secret al
                token_data = json.loads(open(token_file, "r", encoding="utf-8").read())
                client_id     = token_data.get("client_id", "")
                client_secret = token_data.get("client_secret", "")
                refresh_token = token_data.get("refresh_token", "") or credentials.refresh_token

                if not client_id or not client_secret:
                    # credentials dosyasından al
                    if os.path.exists(creds_file):
                        creds_data  = json.loads(open(creds_file, "r", encoding="utf-8").read())
                        installed   = creds_data.get("installed", creds_data)
                        client_id   = installed.get("client_id", "")
                        client_secret = installed.get("client_secret", "")

                r = req_lib.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id":     client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "grant_type":    "refresh_token",
                    },
                    verify=False,
                    timeout=15,
                )
                if r.status_code == 200:
                    new_token = r.json()
                    token_data["token"] = new_token["access_token"]
                    import datetime as _dt
                    expiry = _dt.datetime.utcnow() + _dt.timedelta(seconds=new_token.get("expires_in", 3600))
                    token_data["expiry"] = expiry.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    new_json = json.dumps(token_data, indent=2)
                    with open(token_file, "w", encoding="utf-8") as f:
                        f.write(new_json)
                    print(f"  ✅ Token yenilendi: {token_file}")
                    _update_railway_token(channel, new_json)
                    # Yeni credentials oluştur
                    from google.oauth2.credentials import Credentials
                    credentials = Credentials.from_authorized_user_file(token_file, SCOPES)
                else:
                    print(f"  ⚠ Token refresh HTTP {r.status_code}: {r.text[:100]}")
                    credentials = None
            except Exception as e:
                print(f"  ⚠ Token yenilenemedi ({e})")
                credentials = None
        else:
            credentials = None

    if not credentials or not credentials.valid:
        import platform
        is_railway = os.environ.get("RAILWAY_ENVIRONMENT") is not None
        is_headless = not platform.system() == "Windows"

        if is_railway or is_headless:
            raise RuntimeError(
                f"Token geçersiz veya yok ({channel}). "
                f"Yeni token almak için lokalde 'python create_{channel}_token.py' çalıştır "
                f"ve TOKEN_{channel.upper()} environment variable'ını güncelle."
            )

        if not os.path.exists(creds_file):
            raise FileNotFoundError(
                f"Credentials dosyası bulunamadı: {creds_file}"
            )
        print(f"  → Tarayıcıda YouTube izni gerekiyor ({channel})...")
        flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
        credentials = flow.run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(credentials.to_json())
        print(f"  ✅ Yeni token kaydedildi: {token_file}")

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
