"""
Token Manager — Railway'de environment variable'lardan token dosyalarını oluşturur.
Lokal çalışmada mevcut token.json dosyalarını kullanır.
"""
import os
import json
import base64


def setup_tokens():
    """
    Railway'de TOKEN_SOZLER, TOKEN_TARIH, TOKEN_VIRAL env var'larından
    token dosyalarını oluşturur. Lokal çalışmada atlar.
    """
    token_map = {
        "TOKEN_SOZLER": "token.json",
        "TOKEN_TARIH":  "token_tarih.json",
        "TOKEN_VIRAL":  "token_viral.json",
    }
    creds_map = {
        "CREDENTIALS_SOZLER": "credentials.json",
        "CREDENTIALS_TARIH":  "credentials_tarih.json.json",
        "CREDENTIALS_VIRAL":  "credentials_viral.json",
    }

    for env_key, file_name in {**token_map, **creds_map}.items():
        val = os.environ.get(env_key)
        if val and not os.path.exists(file_name):
            try:
                # Base64 decode dene
                decoded = base64.b64decode(val).decode("utf-8")
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(decoded)
                print(f"  ✅ {file_name} oluşturuldu ({env_key})")
            except Exception as e:
                # Direkt JSON string olabilir
                try:
                    json.loads(val)  # Geçerli JSON mi?
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
    # Token'ları base64'e çevir ve ekrana yaz
    for fname in ["token.json", "token_tarih.json", "token_viral.json",
                  "credentials.json", "credentials_tarih.json.json", "credentials_viral.json"]:
        b64 = get_token_b64(fname)
        if b64:
            env_key = fname.replace(".json","").replace(".","_").upper()
            env_key = env_key.replace("TOKEN_JSON","TOKEN_SOZLER")
            print(f"\n{env_key}={b64[:50]}...")
            print(f"(Tam değer {len(b64)} karakter)")
        else:
            print(f"⚠ {fname} bulunamadı")
