"""
Kanal Konfigürasyonu
"""

TARIH_CHANNEL_ID         = "UC3eEPGHol_F5AJD9D3IzxbA"
NOTESOFHISTORY_CHANNEL_ID = "UCcBwQBE5tPXrT5yyQVlNlrw"  # YouTube Studio'dan al

CHANNELS = {
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
    "notesofhistory": {
        "name":         "Notes of History",
        "icon":         "📖",
        "channel_id":   NOTESOFHISTORY_CHANNEL_ID,
        "color":        "#d97706",
        "token_file":   "token_notesofhistory.json",
        "credentials":  "credentials.json",  # sozler ile paylaşılan OAuth client
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
