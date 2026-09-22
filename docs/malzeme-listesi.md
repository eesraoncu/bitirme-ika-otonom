# Malzeme Listesi

**Stok kontrolü:** 2026-09-22 · Fiyatlar KDV dahil, değişebilir.
Gerekli olduğu faz: **Faz 2.4** (CAN kablolaması). Faz 1 ve Faz 2.1–2.3 için hiçbiri gerekmiyor.

---

## 1. CAN alıcı-verici modülü ×2  — ZORUNLU

En kritik parça. **3,3 V ile çalışan model şart** (5 V modeli kartı bozar).

| Satıcı | Ürün | Fiyat | Stok |
|---|---|---|---|
| **Robiz.net** | SN65HVD230 CAN Modülü SMD | 115,20 TL | ✅ Stokta |
| Ulutaş Elektronik | WCMCU-230 CAN Haberleşme Modülü (65HVD230) | ~196 TL | ✅ 80 adet |
| Robotistan / Direnç / SAMM | — | — | ❌ Yok / tükendi |

**Alırken bak:** Üzerinde 120 Ω sonlandırma direnci var mı ("R2" ya da "120R" yazar).
Yoksa aşağıdaki dirençleri de sipariş et.

## 2. USB-TTL dönüştürücü ×1  — ZORUNLU

Araç kanalı için. **3,3 V seviyesi seçilebilmeli.**

| Satıcı | Ürün | Fiyat | Stok |
|---|---|---|---|
| **Robotistan** | USB 2.0'dan TTL UART Modül 6 Pin - CP2102 | 135,52 TL | ✅ Stokta |

6 pinli model 3,3 V / 5 V jumper'ı olduğu için seçildi. 4 pinli modellerde bu jumper yok.

## 3. Mantık analizörü ×1  — ÖNERİLİR (S1 ölçümü için)

Kart üzerindeki karar süresini (mikrosaniye) ölçmenin tek yolu.
**CY7C68013A / FX2LP çipli olmalı** — sisteme kurulu `sigrok-firmware-fx2lafw` ve PulseView bunu tanır.

| Satıcı | Ürün | Fiyat | Stok |
|---|---|---|---|
| **Amazon.com.tr** | SeenGreat 8 kanal CY7C68013A, sigrok/PulseView uyumlu | — | ✅ Stokta |
| Hepsiburada | Çeşitli satıcılar, 24 MHz 8 kanal | — | ⚠️ <5 adet |
| Robiz.net | USB Lojik Analizör 24 MHz 8 Kanal | 518,40 TL | ⚠️ 10-15 gün |
| Robotistan | USB Lojik Analizör 24 MHz 8 Kanal | 461,84 TL | ❌ Tükendi |
| Direnç.net | Saleae Logic Analyzer 24 MHz 8 Kanal | 418,45 TL | ❌ Tükendi |

## 4. Kablolar ve breadboard  — ZORUNLU

| Satıcı | Ürün | Fiyat | Stok |
|---|---|---|---|
| Robotistan | 40 Pin Dişi-Erkek M-F Jumper Kablo 200 mm | 51,12 TL | ✅ |
| Robotistan | 40 Pin Dişi-Dişi F-F Jumper Kablo 200 mm | 48,15 TL | ✅ |
| Robotistan | Orta Boy Breadboard | 35,54 TL | ✅ |

## 5. 120 Ω direnç ×2  — SİGORTA

CAN modüllerinde sonlandırma direnci yoksa şart. Birkaç lira, almakta fayda var —
olmadan hat çoğu zaman hiç çalışmaz ve sebebini bulmak günler alır.
Direnc.net ya da herhangi bir elektronik mağazasında bulunur.

## 6. Micro-USB veri kablosu  — KONTROL ET

NUCLEO-G474RE micro-USB kullanıyor. **Sadece şarj eden kablo kartı tanıtmaz.**
Kartla birlikte kablo geldiyse yeni almaya gerek yok.

---

## Tahmini maliyet

| Kalem | Tutar |
|---|---|
| 2× CAN modülü (Robiz) | 230 TL |
| USB-TTL (Robotistan) | 136 TL |
| Jumper ×2 + breadboard (Robotistan) | 135 TL |
| 120 Ω direnç ×2 | ~10 TL |
| **Analizör hariç ara toplam** | **~511 TL** |
| Mantık analizörü | ~420–520 TL |
| **Toplam** | **~930–1030 TL** |

Öneride yazılan "~250 TL" tahmini yalnızca CAN modüllerini kapsıyordu; kablolar,
dönüştürücü ve analizör hesaba katılınca rakam bu seviyeye çıkıyor.

## Sipariş notu

Üç ayrı satıcı üç ayrı kargo demek. Hepsi tek yerden alınamıyor çünkü CAN modülü
Robotistan'da yok. En az kargo için: CAN modülleri Robiz'den, kalan her şey
Robotistan'dan, analizör Amazon'dan.
