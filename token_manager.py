"""
Token Manager — Railway'de environment variable'lardan token dosyalarını oluşturur.
Lokal çalışmada mevcut token.json dosyalarını kullanır.
"""
import os
import json
import base64


def setup_tokens():
    """
    Railway'de TOKEN_* env var'larından token dosyalarını oluşturur.
    """
    token_map = {
        "TOKEN_TARIH":          "token_tarih.json",
        "TOKEN_NOTESOFHISTORY": "token_notesofhistory.json",
    }
    creds_map = {
        # credentials.json Notes of History ile paylaşılan OAuth client — env adı legacy
        "CREDENTIALS_SOZLER": "credentials.json",
        "CREDENTIALS_TARIH":  "credentials_tarih.json.json",
    }

    for env_key, file_name in {**token_map, **creds_map}.items():
        val = os.environ.get(env_key)
        if val:
            try:
                decoded = base64.b64decode(val).decode("utf-8")
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(decoded)
                print(f"  ✅ {file_name} oluşturuldu ({env_key})")
            except Exception as e:
                try:
                    json.loads(val)
                    with open(file_name, "w", encoding="utf-8") as f:
                        f.write(val)
                    print(f"  ✅ {file_name} oluşturuldu ({env_key})")
                except:
                    print(f"  ⚠ {env_key} parse edilemedi: {e}")


def get_token_b64(file_name: str) -> str:
    """Token dosyasını base64'e çevirir — Railway env var'a kopyalamak için."""
    if not os.path.exists(file_name):
        return ""
    with open(file_name, "r", encoding="utf-8") as f:
        content = f.read()
    return base64.b64encode(content.encode("utf-8")).decode("ascii")


if __name__ == "__main__":
    for fname in ["token_tarih.json", "token_notesofhistory.json",
                  "credentials.json", "credentials_tarih.json.json"]:
        b64 = get_token_b64(fname)
        if b64:
            print(f"\n{fname}: {len(b64)} karakter")
            print(b64[:80] + "...")
        else:
            print(f"⚠ {fname} bulunamadı")
