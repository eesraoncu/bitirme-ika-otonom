#!/usr/bin/env python3
"""İKA sahasının dokularını üretir (Faz 3).

Kullanım (depo kökünden):
    python3 ros2_ws/src/ika_sim/tools/gen_textures.py

Çıktı ros2_ws/src/ika_sim/worlds/textures/ altına:
    asfalt.jpg    saha zemini, 33 × 21 m, 2 cm/piksel
    konteyner.jpg konteynerin yan yüzü: oluklu metal, pas, etiketler
    yasak.jpg     yasak bölge boyası: sarı-siyah çizgi, aşınmış
    cop.jpg       çöp konteynerinin yüzü: yeşil boyalı metal, ezik, yazı

Neden kendi dokularımız: kamera ile haritalama (RTAB-Map) görüntüde ayırt
edilebilir noktalar arar. Düz renkli yüzeyde nokta yoktur; tekrar eden desende
her yer birbirine benzer ve döngü kapatma yanılır. Dokular bu yüzden
gürültülü ve tekrar etmeyecek şekilde üretilir. Tohum sabit: betik her
çalıştırmada aynı dosyaları üretir, deney tekrarlanabilir kalır.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / 'worlds' / 'textures'
SEED = 2026
FONT = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')


def noise(rng, w, h, scales):
    """Farklı ölçeklerde rastgele ızgaraların büyütülüp toplanması: kaba ve
    ince taneli gürültü birlikte. Sonuç 0..1 arası."""
    out = np.zeros((h, w))
    for cell, weight in scales:
        small = rng.random((max(1, h // cell), max(1, w // cell)))
        img = Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += weight * np.asarray(img) / 255.0
    out -= out.min()
    return out / out.max()


def font(size):
    return ImageFont.truetype(str(FONT), size) if FONT.exists() else ImageFont.load_default()


def asfalt(rng):
    w, h = 1650, 1050   # 33 × 21 m, 2 cm/piksel (K-035)
    # Sayılar metrekare başına yoğunluğu korur: saha 21 × 13'ten 33 × 21'e büyüdü
    # (alan 2,54 kat), leke, çatlak, tane ve işaret sayıları da o kadar arttı
    g = 0.30 + 0.12 * noise(rng, w, h, [(64, 0.5), (16, 0.3), (4, 0.15), (1, 0.4)])
    img = Image.fromarray((np.clip(g, 0, 1) * 255).astype(np.uint8)).convert('RGB')
    d = ImageDraw.Draw(img, 'RGBA')
    # Yağ lekeleri: koyu, yumuşak kenarlı elipsler
    stains = Image.new('L', (w, h), 0)
    ds = ImageDraw.Draw(stains)
    for _ in range(114):
        x, y = rng.integers(0, w), rng.integers(0, h)
        rx, ry = rng.integers(8, 40), rng.integers(6, 30)
        ds.ellipse([x - rx, y - ry, x + rx, y + ry], fill=int(rng.integers(40, 110)))
    stains = stains.filter(ImageFilter.GaussianBlur(6))
    img = Image.composite(Image.new('RGB', (w, h), (25, 25, 28)), img, stains)
    d = ImageDraw.Draw(img, 'RGBA')
    # Çatlaklar: rastgele yürüyüş çizgileri
    for _ in range(76):
        x, y = float(rng.integers(0, w)), float(rng.integers(0, h))
        ang = rng.random() * 2 * np.pi
        pts = [(x, y)]
        for _ in range(int(rng.integers(15, 60))):
            ang += rng.normal(0, 0.5)
            x, y = x + 4 * np.cos(ang), y + 4 * np.sin(ang)
            pts.append((x, y))
        d.line(pts, fill=(20, 20, 20, 200), width=int(rng.integers(1, 3)))
    # Açık renk taneler (agrega)
    for _ in range(15200):
        x, y = rng.integers(0, w), rng.integers(0, h)
        c = int(rng.integers(120, 190))
        d.point((x, y), fill=(c, c, c, 255))
    # Silik zemin işaretleri: birkaç beyaz çizgi parçası ve numara, yer tanımaya yardım eder
    placed = []
    while len(placed) < 20:
        x, y = rng.integers(40, w - 140), rng.integers(40, h - 40)
        if any(abs(x - px) < 170 and abs(y - py) < 60 for px, py in placed):
            continue   # üst üste binmesin
        placed.append((x, y))
        d.rectangle([x, y, x + int(rng.integers(60, 140)), y + 6], fill=(220, 220, 210, 110))
        d.text((x, y + 12), str(int(rng.integers(10, 99))), font=font(28), fill=(220, 220, 210, 110))
    return img


def konteyner(rng):
    w, h = 1024, 440   # 6 × 2,6 m yan yüz
    base = np.array([38, 82, 120], dtype=float)   # soluk lacivert
    x = np.arange(w)
    ridges = 0.82 + 0.18 * (np.sin(x / w * 2 * np.pi * 48) > 0)   # oluklar
    shade = ridges[None, :, None] * (0.85 + 0.3 * noise(rng, w, h, [(32, 0.6), (4, 0.4)]))[:, :, None]
    img = Image.fromarray(np.clip(base * shade, 0, 255).astype(np.uint8))
    # Pas lekeleri
    rust = Image.new('L', (w, h), 0)
    dr = ImageDraw.Draw(rust)
    for _ in range(25):
        cx, cy = rng.integers(0, w), rng.integers(0, h)
        r = int(rng.integers(6, 35))
        dr.ellipse([cx - r, cy - r // 2, cx + r, cy + r], fill=int(rng.integers(80, 200)))
    rust = rust.filter(ImageFilter.GaussianBlur(5))
    img = Image.composite(Image.new('RGB', (w, h), (120, 62, 30)), img, rust)
    d = ImageDraw.Draw(img)
    # Etiketler: kimlik numarası, uyarı levhası, kapı kolu çizgileri
    d.text((40, 30), f"IKAU {int(rng.integers(100000, 999999))} {int(rng.integers(0, 9))}",
           font=font(42), fill=(235, 235, 235))
    d.text((40, 85), "22G1   MAX GROSS 30480 KG", font=font(22), fill=(235, 235, 235))
    for i in range(4):
        xx = 560 + i * 60
        d.rectangle([xx, 80, xx + 6, h - 60], fill=(70, 70, 70))
    d.rectangle([w - 200, 60, w - 70, 180], fill=(240, 200, 20))
    d.text((w - 188, 100), "UN 1203", font=font(24), fill=(20, 20, 20))
    return img


def yasak(rng):
    w = h = 512
    yy, xx = np.mgrid[0:h, 0:w]
    stripe = ((xx + yy) // 48) % 2 == 0
    rgb = np.where(stripe[:, :, None], np.array([235, 190, 20]), np.array([25, 25, 25]))
    # Aşınma: yer yer boyanın altındaki asfalt görünür
    wear = noise(rng, w, h, [(32, 0.6), (4, 0.4)]) > 0.72
    rgb = np.where(wear[:, :, None], np.array([80, 80, 80]), rgb)
    return Image.fromarray(rgb.astype(np.uint8))


def cop(rng):
    w, h = 640, 416   # 2,0 × 1,3 m yan yüz
    base = np.array([40, 92, 52], dtype=float)   # koyu yeşil
    shade = 0.75 + 0.35 * noise(rng, w, h, [(48, 0.6), (6, 0.3), (1, 0.1)])
    img = Image.fromarray(np.clip(base * shade[:, :, None], 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img, 'RGBA')
    # Ezikler: koyu, yumuşak lekeler; üst kenarda kapak çizgisi
    for _ in range(12):
        x, y = rng.integers(0, w), rng.integers(60, h)
        r = int(rng.integers(10, 30))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(10, 30, 15, 90))
    d.rectangle([0, 0, w, 40], fill=(25, 60, 35, 255))
    d.text((60, 150), "ATIK", font=font(110), fill=(230, 230, 220, 230))
    d.text((60, 290), f"NO {int(rng.integers(100, 999))}", font=font(40), fill=(230, 230, 220, 200))
    return img


def main():
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in [('asfalt', asfalt), ('konteyner', konteyner), ('yasak', yasak),
                       ('cop', cop)]:
        path = OUT / f'{name}.jpg'
        make(rng).save(path, quality=90)
        print(f'{path.relative_to(OUT.parents[4])}: {path.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main()
