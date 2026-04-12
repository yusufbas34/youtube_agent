"""
Söz Yöneticisi
- Kullanılan sözleri used_quotes.json'a kaydeder
- Silinen sözleri deleted_quotes.json'a kaydeder
- Her iki listede olan sözler bir daha asla gösterilmez
- Metin bazlı kontrol yapar (ID değişse bile aynı metin tekrar gelmez)
"""

import json, os
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY

QUOTES_FILE      = "quotes.json"
USED_QUOTES_FILE = "used_quotes.json"
DELETED_FILE     = "deleted_quotes.json"


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_quotes():  return load_json(QUOTES_FILE)
def save_quotes(q): save_json(QUOTES_FILE, q)


def get_blocked_texts() -> set:
    """Kullanılan + silinen tüm söz metinlerini döner (metin bazlı)."""
    blocked = set()

    # Kullanılanlar
    for q in load_json(USED_QUOTES_FILE):
        t = q.get("text","").strip().lower()
        if t: blocked.add(t)

    # Silinenler
    for q in load_json(DELETED_FILE):
        t = q.get("text","").strip().lower()
        if t: blocked.add(t)

    return blocked


def get_blocked_ids() -> set:
    """Silinen söz ID'lerini döner."""
    return {q.get("id","") for q in load_json(DELETED_FILE)}


def is_blocked(quote: dict, blocked_texts: set, blocked_ids: set) -> bool:
    """Söz bloklu mu kontrol eder."""
    if quote.get("id","") in blocked_ids:
        return True
    if quote.get("text","").strip().lower() in blocked_texts:
        return True
    if quote.get("used"):
        return True
    return False


def fetch_quotes_claude(category: str, count: int = 10) -> list:
    """Claude ile geniş kaynaklardan söz üretir."""
    import httpx
    http   = httpx.Client(verify=False)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)

    cat_descs = {
        "motivasyon":      "motivasyon, başarı, azim, hedef, güç, kararlılık",
        "kisisel_gelisim": "kişisel gelişim, öz-farkındalık, büyüme, alışkanlıklar",
        "ozlu_soz":        "özlü derin felsefi bilgelik sözleri",
        "unlu_alinti":     "Einstein, Atatürk, Mevlana, Marcus Aurelius, Steve Jobs, Konfüçyüs, Yunus Emre, Rumi gibi ünlülerden",
        "dini":            "Kuran ayetleri, hadisler, dini ve manevi evrensel sözler",
        "ask_iliskiler":   "aşk, ilişkiler, kalp, özlem, sevgi, bağlılık",
        "yasam_felsefesi": "yaşam felsefesi, mutluluk, anlam, varoluş, huzur",
    }
    desc = cat_descs.get(category, "genel ilham verici")

    prompt = f"""
Sen sosyal medya içerik uzmanısın. Instagram ve TikTok'ta viral olan, {desc} konusunda {count} adet güçlü Türkçe söz üret.

Kaynak çeşitliliği şart — bunlardan karışık kullan:
- Ünlü kişi alıntıları (Türk ve dünya)
- Türk şarkılarından viral dizeler
- Twitter ve Instagram'da çok paylaşılan anonim sözler
- Türk atasözleri ve deyimler
- Batı filozofları Türkçe çeviri (Stoikler, Nietzsche, Seneca)
- Film ve dizi repliklerinden viral olanlar

Kriterler:
- Kısa ve güçlü (max 140 karakter)
- Akılda kalıcı, duygusal etki yüksek
- Her söz farklı bir kaynaktan olsun

Sadece geçerli JSON döndür:
[
  {{
    "text": "söz metni",
    "author": "Yazar adı veya Anonim",
    "category": "{category.replace('_', ' ')}",
    "source": "sarki/alinti/atasoz/ayet/replik/internet/felsefe",
    "original": null,
    "viral_score": 8
  }}
]
"""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = msg.content[0].text.strip()
    if "```json" in text: text = text.split("```json")[1].split("```")[0]
    elif "```" in text:   text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def refresh_quotes(force: bool = False) -> list:
    """Tüm kategorilerde yeni sözler üretir."""
    blocked_texts = get_blocked_texts()
    blocked_ids   = get_blocked_ids()
    existing      = load_quotes()

    # Mevcut kullanılabilir sözler
    available = [q for q in existing if not is_blocked(q, blocked_texts, blocked_ids)]

    if len(available) >= 15 and not force:
        print(f"  → {len(available)} kullanılabilir söz var, güncelleme atlandı.")
        return existing

    categories = [
        "motivasyon", "kisisel_gelisim", "ozlu_soz",
        "unlu_alinti", "dini", "ask_iliskiler", "yasam_felsefesi"
    ]

    existing_texts = {q.get("text","").strip().lower() for q in existing}
    all_new = []

    for cat in categories:
        print(f"  → '{cat}' kategorisi üretiliyor...")
        try:
            new_q = fetch_quotes_claude(cat, count=8)
            added = 0
            for q in new_q:
                txt = q.get("text","").strip()
                txt_lower = txt.lower()
                # Bloklu veya mevcut metinse atla
                if txt_lower in blocked_texts: continue
                if txt_lower in existing_texts: continue
                ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[-10:]
                q["id"]         = f"q_{cat[:4]}_{ts}_{len(all_new):03d}"
                q["used"]       = False
                q["used_at"]    = None
                q["video_url"]  = None
                q["created_at"] = datetime.now().isoformat()
                all_new.append(q)
                existing_texts.add(txt_lower)
                added += 1
            print(f"     {added} yeni söz eklendi.")
        except Exception as e:
            print(f"  ⚠ '{cat}' hatası: {e}")

    # Bloklu olmayanları koru + yenileri ekle
    kept = [q for q in existing if not is_blocked(q, blocked_texts, blocked_ids)]
    final = kept + all_new
    save_quotes(final)
    print(f"\n  ✅ {len(all_new)} yeni söz. Toplam aktif: {len(final)}")
    return final


def get_next_quote(category: str = None, selected_id: str = None) -> dict:
    """Sıradaki sözü döner — kullanılan ve silinenleri atlar."""
    quotes        = load_quotes()
    blocked_texts = get_blocked_texts()
    blocked_ids   = get_blocked_ids()

    if selected_id:
        q = next((q for q in quotes if q["id"] == selected_id), None)
        if q: return q

    available = [q for q in quotes if not is_blocked(q, blocked_texts, blocked_ids)]

    if category:
        cat_q = [q for q in available if q.get("category","").lower().find(category.lower()) >= 0]
        if cat_q: available = cat_q

    if not available:
        print("  ⚠ Kullanılabilir söz kalmadı, yeniler üretiliyor...")
        refresh_quotes(force=True)
        quotes        = load_quotes()
        blocked_texts = get_blocked_texts()
        blocked_ids   = get_blocked_ids()
        available     = [q for q in quotes if not is_blocked(q, blocked_texts, blocked_ids)]

    available.sort(key=lambda q: q.get("viral_score", 5), reverse=True)
    return available[0]


def mark_quote_used(quote_id: str, video_url: str = None):
    """Sözü kullanıldı olarak işaretle ve used_quotes.json'a kaydet."""
    quotes = load_quotes()
    used   = load_json(USED_QUOTES_FILE)

    for q in quotes:
        if q["id"] == quote_id:
            q["used"]      = True
            q["used_at"]   = datetime.now().isoformat()
            q["video_url"] = video_url

            # used_quotes.json'a ekle (metin bazlı tekrar kontrolü)
            existing_used_texts = {u.get("text","").strip().lower() for u in used}
            if q["text"].strip().lower() not in existing_used_texts:
                used.append({
                    "id":        q["id"],
                    "text":      q["text"],
                    "author":    q.get("author",""),
                    "category":  q.get("category",""),
                    "used_at":   q["used_at"],
                    "video_url": video_url
                })
            break

    save_quotes(quotes)
    save_json(USED_QUOTES_FILE, used)
    print(f"  ✅ Söz kullanıldı olarak işaretlendi ve kaydedildi.")


def delete_quote(quote_id: str, text: str = "", author: str = ""):
    """Sözü sil ve deleted_quotes.json'a kaydet."""
    quotes  = load_quotes()
    deleted = load_json(DELETED_FILE)

    # quotes.json'dan kaldır
    q = next((q for q in quotes if q["id"] == quote_id), None)
    if q:
        text   = q.get("text","")
        author = q.get("author","")
        quotes = [x for x in quotes if x["id"] != quote_id]
        save_quotes(quotes)

    # deleted_quotes.json'a ekle (metin bazlı tekrar kontrolü)
    existing_del_texts = {d.get("text","").strip().lower() for d in deleted}
    if text.strip().lower() not in existing_del_texts:
        deleted.append({
            "id":         quote_id,
            "text":       text,
            "author":     author,
            "deleted_at": datetime.now().isoformat()
        })
        save_json(DELETED_FILE, deleted)
    print(f"  ✅ Söz silindi ve kaydedildi.")


def get_stats() -> dict:
    """Söz istatistiklerini döner."""
    quotes   = load_quotes()
    used     = load_json(USED_QUOTES_FILE)
    deleted  = load_json(DELETED_FILE)
    blocked  = get_blocked_texts()
    blocked_ids = get_blocked_ids()
    available = [q for q in quotes if not is_blocked(q, blocked, blocked_ids)]

    return {
        "total":     len(quotes),
        "available": len(available),
        "used":      len(used),
        "deleted":   len(deleted),
        "blocked":   len(blocked)
    }


if __name__ == "__main__":
    stats = get_stats()
    print(f"Söz istatistikleri:")
    print(f"  Toplam: {stats['total']}")
    print(f"  Kullanılabilir: {stats['available']}")
    print(f"  Kullanılan: {stats['used']}")
    print(f"  Silinen: {stats['deleted']}")
    print(f"  Bloklu (metin): {stats['blocked']}")
