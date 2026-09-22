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

## 3. Mantık analizörü — İLK SİPARİŞE DAHİL DEĞİL (bkz. K-009)

Karar süresi Faz 2.6'da **DWT çevrim sayacıyla** ölçülecek (170 MHz'de 5,9 ns
çözünürlük — 24 MHz analizörden ~7 kat hassas). Analizör şu iki durumda alınır:
Faz 2.4'te CAN hattı çözülemezse, ya da Faz 5 öncesi bağımsız doğrulama için.

**Alınırsa CY7C68013A / FX2LP çipli olmalı** — kurulu `sigrok-firmware-fx2lafw`
ve PulseView yalnızca bunları tanır.

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

## 6. Micro-USB VERİ kablosu ×1  — ZORUNLU

**Doğrulandı (2026-09-22):** Kart **NUCLEO-G474RE, MB1367/C** revizyonu ve
CN1 konektörü **micro-USB**. Mini değil.

Elde bulunan JBL bluetooth hoparlör kablosu denendi: karta besleme gidiyor
(LD3 kırmızı güç LED'i yanıyor) ama `lsusb` çıktısında ST cihazı görünmüyor —
kabloda **veri telleri yok**, yalnızca güç telleri var. Kullanılamaz.

Adında **"data"** geçen model alınmalı; "güç aktarım kablosu" diye geçenler
çoğunlukla yalnızca besleme taşır.

| Satıcı | Ürün | Fiyat | Stok |
|---|---|---|---|
| **Robotistan** | Micro USB 15cm Data Kablosu - Siyah | 21,41 TL | ✅ Stokta |
| Robotistan | Mikro USB Kablo 1.5 m (masada daha rahat) | 74,33 TL | ✅ Stokta |

**Bu kablo gelmeden Faz 0'ın LED testi (plan 3.6) ve Faz 2'nin tamamı yapılamaz.**
Siparişte en öncelikli kalem budur.

---

## Tahmini maliyet

### İlk sipariş (verilecek)

| Kalem | Tutar |
|---|---|
| 2× CAN modülü (Robiz) | 230 TL |
| USB-TTL (Robotistan) | 136 TL |
| Jumper ×2 + breadboard (Robotistan) | 135 TL |
| 120 Ω direnç ×2 | ~10 TL |
| Micro-USB **data** kablosu (Robotistan) | 21 TL |
| **Toplam** | **~532 TL** |

### Ertelenen

| Kalem | Tutar | Ne zaman |
|---|---|---|
| Mantık analizörü | ~420–520 TL | K-009'daki tetikleyicilerden biri olursa |

Öneride yazılan "~250 TL" tahmini yalnızca CAN modüllerini kapsıyordu; kablolar ve
dönüştürücü hesaba katılınca ilk sipariş ~511 TL'ye çıkıyor.

## Sipariş notu

CAN modülü Robotistan'da olmadığı için tek satıcıdan alınamıyor.
En az kargo: **CAN modülleri Robiz'den, kalan her şey Robotistan'dan** → 2 kargo.
