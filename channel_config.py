"""
Kanal Konfigürasyonu
"""

SOZLER_CHANNEL_ID        = "UCaWkRsWG0rSKyfnNJ5T9eXA"
TARIH_CHANNEL_ID         = "UC3eEPGHol_F5AJD9D3IzxbA"
VIRAL_CHANNEL_ID         = "UCWNVRMZjIg9DuS-Ig_LmSLw"
NOTESOFHISTORY_CHANNEL_ID = "UCcBwQBE5tPXrT5yyQVlNlrw"  # YouTube Studio'dan al

CHANNELS = {
    "sozler": {
        "name":         "Sözler Kanalı",
        "icon":         "💬",
        "channel_id":   SOZLER_CHANNEL_ID,
        "color":        "#7c3aed",
        "token_file":   "token.json",
        "credentials":  "credentials.json",
        "output_dir":   "output/sozler",
        "queue_file":   "data/sozler_queue.json",
        "history_file": "data/sozler_history.json",
    },
    "tarih": {
        "name":         "Tarih Kanalı",
        "icon":         "📜",
        "channel_id":   TARIH_CHANNEL_ID,
        "color":        "#b45309",
        "token_file":   "token_tarih.json",
        "credentials":  "credentials_tarih.json.json",
        "output_dir":   "output/tarih",
        "queue_file":   "data/tarih_queue.json",
        "history_file": "data/tarih_history.json",
    },
    "viral": {
        "name":         "Viral Kanalı",
        "icon":         "⚡",
        "channel_id":   VIRAL_CHANNEL_ID,
        "color":        "#dc2626",
        "token_file":   "token_viral.json",
        "credentials":  "credentials_viral.json",
        "output_dir":   "output/viral",
        "queue_file":   "data/viral_queue.json",
        "history_file": "data/viral_history.json",
    },
    "notesofhistory": {
        "name":         "Notes of History",
        "icon":         "📖",
        "channel_id":   NOTESOFHISTORY_CHANNEL_ID,
        "color":        "#d97706",
        "token_file":   "token_notesofhistory.json",
        "credentials":  "credentials.json",
        "output_dir":   "output/notesofhistory",
        "queue_file":   "data/notesofhistory_queue.json",
        "history_file": "data/notesofhistory_history.json",
    },
}

HISTORY_VIDEO_FORMATS = {
    "timeline":    {"weight": 1.0, "description": "Animasyonlu timeline + metin"},
    "illustrated": {"weight": 1.0, "description": "Illustrasyon + anlati"},
    "simple":      {"weight": 1.0, "description": "Metin + arka plan video"},
}
