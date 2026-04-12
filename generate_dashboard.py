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
    # Hem yeni hem eski yollardan upload history yükle
    upload = (load_json("data/sozler_history.json") or
              load_json("upload_history.json") or [])

    data = {
        "upload":    upload,
        "perf":      load_json("performance_report.json") or {},
        "trend":     load_json("trend_analysis.json")     or {},
        "content":   load_json("content_plan.json")       or {},
        "quotes":    load_json("quotes.json")              or [],
        "roadmap":   load_json("data/roadmap_cache.json")  or {},
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
    print("Tamamlandı!")
