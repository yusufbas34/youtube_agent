"""
Sahne İllüstrasyon Üretici
Stok görsel/video aramasının yerini alır — tamamen yerelde, PIL ile
çizilen düz-tasarım (flat illustration) sahneler üretir. Dış API
gerektirmez, dolayısıyla "alakasız görsel geldi" / "görsel gelmiyor"
sorunlarının kök nedenini (stok arama güvenilmezliği) ortadan kaldırır.
"""
import random
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920


def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _lerp(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _vgrad(draw, top, bottom, y0=0, y1=H):
    for y in range(y0, y1):
        t = (y - y0) / max(1, (y1 - y0))
        draw.line([(0, y), (W, y)], fill=_lerp(top, bottom, t))


def _add_grain(img, amount=10):
    noise = Image.effect_noise((W, H), amount).convert("L")
    noisy = Image.merge("RGB", [noise, noise, noise])
    return Image.blend(img, noisy, 0.04)


def _add_vignette(img):
    vign = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vign)
    vd.ellipse([-W * 0.3, -H * 0.2, W * 1.3, H * 1.1], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(220))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(img, dark, vign)


# ── Şablonlar ────────────────────────────────────────────────────

def scene_castle(accent, dusk=(20, 10, 30), horizon=(90, 50, 40)):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    _vgrad(d, dusk, horizon, 0, int(H * 0.62))
    _vgrad(d, horizon, (8, 5, 10), int(H * 0.55), H)
    d.ellipse([W * 0.5 - 140, H * 0.30 - 140, W * 0.5 + 140, H * 0.30 + 140],
              fill=_lerp(accent, (255, 235, 200), 0.4))
    base_y = int(H * 0.62)
    towers = [(0.08, 0.20, 0.16), (0.30, 0.12, 0.10), (0.50, 0.26, 0.20),
              (0.70, 0.14, 0.11), (0.92, 0.22, 0.17)]
    silh = (8, 5, 12)
    for cx, w, h in towers:
        x = int(W * cx); tw = int(W * w); th = int(H * h)
        d.rectangle([x - tw // 2, base_y - th, x + tw // 2, base_y + 40], fill=silh)
        d.polygon([(x - tw // 2 - 10, base_y - th), (x + tw // 2 + 10, base_y - th),
                    (x, base_y - th - int(th * 0.35))], fill=silh)
    d.rectangle([0, base_y + 20, W, H], fill=silh)
    return img


def scene_army(accent, sky=(35, 15, 10), ground=(10, 6, 6)):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    _vgrad(d, sky, (70, 35, 15), 0, int(H * 0.55))
    _vgrad(d, (50, 25, 12), ground, int(H * 0.5), H)
    silh = (6, 4, 4)
    base_y = int(H * 0.72)
    rnd = random.Random(7)
    for i in range(26):
        x = int(W * (i / 25) + rnd.uniform(-14, 14))
        hh = rnd.randint(140, 220)
        d.line([(x, base_y), (x, base_y - hh)], fill=silh, width=5)
        d.polygon([(x - 14, base_y - hh + 40), (x + 14, base_y - hh + 40),
                    (x, base_y - hh - 18)], fill=silh)
        d.ellipse([x - 20, base_y - 50, x + 20, base_y - 10], fill=silh)
    d.rectangle([0, base_y, W, H], fill=silh)
    return img


def scene_ship(accent, sky=(10, 20, 35), sea=(5, 12, 22)):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    _vgrad(d, sky, (120, 90, 60), 0, int(H * 0.5))
    _vgrad(d, (60, 70, 70), sea, int(H * 0.5), H)
    silh = (4, 6, 10)
    base_y = int(H * 0.56)
    for row in range(4):
        y = base_y + row * 70
        pts = [(0, y)]
        for x in range(0, W + 60, 60):
            yy = y + (18 if (x // 60) % 2 == 0 else -8) + row * 4
            pts.append((x, yy))
        pts += [(W, H), (0, H)]
        shade = _lerp(sea, (0, 0, 0), row * 0.18)
        d.polygon(pts, fill=shade)
    cx = int(W * 0.5); hull_y = base_y - 10
    d.polygon([(cx - 170, hull_y), (cx + 170, hull_y), (cx + 120, hull_y + 70),
                (cx - 120, hull_y + 70)], fill=silh)
    d.line([(cx, hull_y), (cx, hull_y - 300)], fill=silh, width=8)
    d.polygon([(cx, hull_y - 300), (cx, hull_y - 60), (cx + 150, hull_y - 70)], fill=silh)
    d.polygon([(cx, hull_y - 260), (cx, hull_y - 60), (cx - 130, hull_y - 80)], fill=silh)
    return img


def scene_crown(accent, bg1=(15, 8, 25), bg2=(45, 15, 35)):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    _vgrad(d, bg1, bg2, 0, H)
    cx, cy = W // 2, int(H * 0.42)
    gold = _lerp(accent, (255, 230, 150), 0.5)
    pts = [(cx - 200, cy + 120), (cx - 200, cy - 10), (cx - 120, cy + 40), (cx - 60, cy - 120),
           (cx, cy + 10), (cx + 60, cy - 120), (cx + 120, cy + 40), (cx + 200, cy - 10),
           (cx + 200, cy + 120)]
    d.polygon(pts, fill=gold)
    d.rectangle([cx - 200, cy + 120, cx + 200, cy + 170], fill=gold)
    for px, py in [(cx - 200, cy - 10), (cx - 60, cy - 120), (cx + 60, cy - 120), (cx + 200, cy - 10)]:
        d.ellipse([px - 16, py - 16, px + 16, py + 16], fill=_lerp(accent, (255, 80, 80), 0.5))
    return img


def scene_temple(accent, sky=(50, 35, 20), ground=(20, 15, 10)):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    _vgrad(d, sky, (150, 100, 55), 0, int(H * 0.58))
    _vgrad(d, (90, 60, 35), ground, int(H * 0.5), H)
    silh = (10, 7, 5)
    base_y = int(H * 0.66)
    d.rectangle([W * 0.1, base_y, W * 0.9, base_y + 36], fill=silh)
    n = 7
    for i in range(n):
        x = int(W * 0.14 + i * (W * 0.72 / (n - 1)))
        d.rectangle([x - 20, base_y - 280, x + 20, base_y], fill=silh)
        d.ellipse([x - 26, base_y - 300, x + 26, base_y - 260], fill=silh)
    d.polygon([(W * 0.08, base_y - 280), (W * 0.92, base_y - 280),
                (W * 0.96, base_y - 320), (W * 0.04, base_y - 320)], fill=silh)
    return img


def scene_abstract(accent, bg1=(10, 10, 20), bg2=(30, 15, 10)):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    _vgrad(d, bg1, bg2, 0, H)
    cx, cy = W // 2, int(H * 0.38)
    for radius in range(560, 0, -24):
        ratio = 1 - radius / 560
        col = _lerp(bg2, accent, ratio * 0.55)
        d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=col)
    return img


TEMPLATES = {
    "castle":   scene_castle,
    "army":     scene_army,
    "ship":     scene_ship,
    "crown":    scene_crown,
    "temple":   scene_temple,
    "abstract": scene_abstract,
}

KEYWORDS = {
    "castle":   ["castle", "fortress", "wall", "siege", "gate", "palace", "citadel"],
    "army":     ["army", "soldier", "battle", "war", "march", "troops", "warrior", "spear", "sword", "combat"],
    "ship":     ["ship", "sea", "ocean", "naval", "fleet", "sail", "voyage", "harbor", "boat"],
    "crown":    ["king", "queen", "emperor", "sultan", "throne", "crown", "royal", "ruler", "dynasty"],
    "temple":   ["temple", "ancient", "rome", "greek", "column", "ruins", "civilization", "empire"],
}


def pick_template(visual_desc: str, seg_idx: int = 0) -> str:
    text = (visual_desc or "").lower()
    for key, words in KEYWORDS.items():
        if any(w in text for w in words):
            return key
    order = list(TEMPLATES.keys())
    return order[seg_idx % len(order)]


def generate_illustration(visual_desc: str, accent_hex: str, seg_idx: int = 0) -> Image.Image:
    """Segment açıklamasına göre bir illüstrasyon sahnesi üretir."""
    accent = hex_to_rgb(accent_hex)
    key = pick_template(visual_desc, seg_idx)
    img = TEMPLATES[key](accent)
    img = _add_vignette(img)
    img = _add_grain(img)
    return img
