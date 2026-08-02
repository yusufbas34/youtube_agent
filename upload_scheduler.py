"""
Ağ Yardımcısı
- Şirket ağı kontrolü yapar (yükleme şirket ağındayken engellenir)
"""

import socket, logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scheduler")

# Şirket ağı tespiti — bu IP/hostname'leri kendi ağına göre düzenle
COMPANY_NETWORK_HINTS = [
    "10.60.",      # Şirket ağı IP aralığı (ekrandan gördüğümüz: 10.60.174.211)
    "10.0.",
    "172.16.",
]


def get_local_ip() -> str:
    """Bilgisayarın yerel IP adresini döner."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"


def is_company_network() -> bool:
    """Şirket ağında mı kontrol eder."""
    ip = get_local_ip()
    for hint in COMPANY_NETWORK_HINTS:
        if ip.startswith(hint):
            log.info(f"Şirket ağı tespit edildi: {ip} — yükleme atlanıyor")
            return True
    log.info(f"Ev/dış ağ: {ip} — yükleme yapılabilir")
    return False
