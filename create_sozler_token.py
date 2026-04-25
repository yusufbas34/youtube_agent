"""
Sözler kanalı için YouTube token oluşturur.
Çalıştır: python create_sozler_token.py
Tarayıcıda Sözler kanalını seç!
"""
import os, json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]
CREDS  = "credentials.json"
TOKEN  = "token.json"

print("Sözler kanalı için YouTube yetkilendirme başlıyor...")
print("ÖNEMLİ: Tarayıcıda açılacak sayfada SÖZLER kanalını seç!")
print()

flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
creds = flow.run_local_server(port=8080)

with open(TOKEN, "w") as f:
    f.write(creds.to_json())

print(f"\nSözler token kaydedildi: {TOKEN}")

# Base64 çıktısı ver — Railway'e yapıştır
import base64
with open(TOKEN, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
print(f"\n--- Railway TOKEN_SOZLER değeri ---")
print(b64)
