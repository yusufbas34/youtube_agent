import json, os, base64
from datetime import datetime

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return None

def generate_dashboard():
    data = {
        "roadmap":    load_json("data/roadmap_cache.json")  or {},
        "tarih_hist": load_json("data/tarih_history.json")  or [],
        "notes_hist": load_json("data/notesofhistory_history.json") or [],
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    b64 = base64.b64encode(
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    template = open("dashboard_template.html", "r", encoding="utf-8").read()
    output   = template.replace("__DATA_B64__", b64)
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(output)
    print("  Dashboard güncellendi: dashboard.html")

if __name__ == "__main__":
    generate_dashboard()
    print("Tamamlandi!")
