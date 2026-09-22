# Malzeme Listesi

**Stok kontrolü:** 2026-09-22 · Fiyatlar KDV dahil, değişebilir.
**Gerekli olduğu faz:** Micro-USB kablo hemen (Faz 0 LED testi için), kalanı Faz 2.4 (CAN kablolaması).
Faz 1 ve Faz 2.1–2.3 için hiçbiri gerekmiyor.

---

## Sipariş: tek satıcı, tek kargo (Robiz.net)

| # | Ürün | Adet | Birim | Tutar | Bağlantı |
|---|---|---|---|---|---|
| 1 | SN65HVD230 CAN Modülü SMD | 2 | 115,20 | **230,40** | robiz.net/sn65hvd230 |
| 2 | USB to TTL UART CP2102 Modül | 1 | 161,28 | **161,28** | robiz.net/cp2102module |
| 3 | 30cm Micro USB Kablo (data) | 1 | 37,44 | **37,44** | robiz.net/microusb30cm |
| 4 | 30cm 40 Pin Erkek-Dişi (M-F) Dupont | 1 | 60,00 | **60,00** | robiz.net/30cmdupontmalefemale40pin |
| 5 | 20cm 40 Pin Dişi-Dişi (F-F) Dupont | 1 | 43,20 | **43,20** | robiz.net/20cmdupontff40 |
| 6 | 20cm 40 Pin Erkek-Erkek (M-M) Dupont | 1 | 43,20 | **43,20** | robiz.net/20cmdupontmm40 |
| 7 | MB-102 Breadboard (830 delik) | 1 | 80,64 | **80,64** | robiz.net/mb102 |
| | | | | **656,16 TL** | |

Hepsi **stokta** (2026-09-22 kontrolü).

---

## Neden bu modeller

### 1 · CAN alıcı-verici ×2 — SN65HVD230

CAN veri yolu iki tel (CANH/CANL) üzerinde farksal sinyal kullanır; STM32'nin FDCAN
birimi ise tek uçlu dijital sinyal üretir. Alıcı-verici bu ikisi arasında çeviri yapar.
**İki adet** çünkü iki CAN düğümü var (FDCAN1 = bekçi tarafı, FDCAN2 = araç tarafı) ve
her düğümün kendi alıcı-vericisi olmak zorunda (bkz. K-002).

**3,3 V şart.** G474 mantık seviyesi 3,3 V; 5 V'luk bir alıcı-verici RX pinini bozabilir.

### 2 · USB-TTL — CP2102 (CH340G değil)

**Kritik ayrım: modüldeki "3.3V" ve "5V" pinleri besleme çıkışıdır, mantık seviyesi
seçici değildir.** TXD'nin kaç voltta sinyal ürettiğini çipin kendi beslemesi belirler.

- **CP2102:** yapısal olarak 3,3 V'luk bir çip (içinde regülatör var) → TXD **her zaman
  3,3 V**. Ayar yok, yanlış ayarlama ihtimali yok.
- **CH340G:** 5 V'ta da 3,3 V'ta da çalışabilir, jumper'a bağlı. Ucuz modüllerde jumper
  bazen yalnızca başlıktaki VCC pinini değiştirir, çip 5 V'ta kalır ve **TXD'den 5 V çıkar**.
  Hangi tasarım olduğunu anlamak multimetre ister.

26 TL fark, bu belirsizliği tamamen ortadan kaldırdığı için ödendi.

### 3 · Micro-USB **data** kablosu

**Kart kimliği doğrulandı (2026-09-22):** NUCLEO-G474RE, **MB1367/C** revizyonu,
CN1 konektörü **micro-USB** (mini değil).

Eldeki JBL bluetooth hoparlör kablosu denendi ve **çalışmadı**: karta besleme gidiyor
(LD3 kırmızı güç LED'i yanıyor) ama `lsusb` çıktısında ST cihazı görünmüyor — kabloda
veri telleri yok.

Seçilen kabloda veri desteği ürün açıklamasında açık: "Data transfer hızı 480 Mb/s",
"USB A / Micro USB B **5 pin** kablo", EMI/RF korumalı. Şarj kabloları 5 iletkenin
hepsini bağlamaz.

**Bu kablo gelmeden Faz 0'ın LED testi (plan 3.6) ve Faz 2'nin tamamı yapılamaz.
Siparişin en öncelikli kalemi budur.**

### 4-6 · Üç tip jumper

Kural: kablonun ucu, bağlanacağı şeyin **tersi** olmalı.

| Taraf | Konektörü |
|---|---|
| CAN modülü ve CP2102 pinleri | erkek |
| Nucleo **Morpho** başlıkları (CN7/CN10) | erkek |
| Nucleo **Arduino** başlıkları (CN5–CN9) | dişi |
| Breadboard delikleri | erkek pin kabul eder |

| Bağlantı | Kablo |
|---|---|
| Breadboard → Nucleo Morpho · Nucleo 3V3/GND → breadboard | **M-F** (en çok kullanılan) |
| Breadboard'da sıra atlama, orta kanalı geçme | **M-M** |
| Modülü doğrudan Morpho'ya bağlama (breadboard'sız) | **F-F** |

### 7 · MB-102 Breadboard (830 delik)

Tam boy (165 mm) seçildi: iki CAN modülü + USB-TTL + sonlandırma dirençleri aynı
tahtaya sığmalı. Modülleri sabitler, ölçüm sırasında tel oynamasını önler.

**Not:** Robiz'de "Breadboard Seti" (180 TL) de var — MB-102 + 65 M-M kablo + 3,3V/5V
güç kaynağı modülü. Alınmadı: güç kaynağı modülü gereksiz (CAN modüllerini Nucleo'nun
3V3 pini besleyecek) ve ayrı alım 56 TL daha ucuza geliyor.

---

## Siparişe DAHİL DEĞİL

### 120 Ω sonlandırma direnci ×2 — modüller gelince karar verilecek

CAN hattı bir iletim hattıdır; uçları boşta kalırsa sinyal geri yansır ve bitleri bozar.
Hattın **her iki ucunda** CANH-CANL arasına 120 Ω direnç gerekir (büklümlü çift CAN
kablosunun karakteristik empedansı budur; ikisi paralel olunca veri yolu 60 Ω görür).

**Ama SN65HVD230 modüllerinin çoğunda bu direnç kart üzerinde hazır gelir** — üzerinde
"R2" ya da "120R" yazar.

**Yapılacak:** Modüller gelince üzerlerine bak.
- Varsa → hiçbir şey alma. Dört sonlandırma olursa veri yolu 30 Ω görür, sinyal
  seviyeleri bozulur ve bu "hiç çalışmama"dan daha sinsi bir hatadır (arada paket kaybı).
- Yoksa → mahalledeki elektronikçiden al, tanesi birkaç lira, aynı gün elinde olur.

Online durumu (2026-09-22): Robiz ❌ katalogda yok (600 parçalık direnç setinde bile
120 Ω atlanmış) · Robotistan ❌ 1/4 W ve 2 W'lık modellerin ikisi de tükendi ·
Direnc.net ✅ 0,17 TL/adet ama **min 50 adet** ve üçüncü bir kargo demek.
8,50 TL'lik direnç için kargo ödemek mantıksız.

**Güç hesabı (1/4 W yeterli mi):** Baskın durumda CANH-CANL arası ~2 V, veri yolu 60 Ω,
toplam akım ~33 mA, her dirençte ~16,7 mA.
`P = I²R = (0,0167)² × 120 ≈ 33 mW` — 1/4 W (250 mW) bunun 7,5 katı. Fazlasıyla yeterli,
2 W gereksiz. Tolerans %5 yeterli. **Delikli (aksiyal) olmalı, SMD breadboard'a takılmaz.**

### Mantık analizörü — ertelendi (bkz. K-009)

Karar süresi Faz 2.6'da **DWT çevrim sayacıyla** ölçülecek: 170 MHz'de 5,9 ns çözünürlük,
24 MHz'lik analizörün 41,7 ns'sinden ~7 kat hassas.

**Alınma koşulu:** Faz 2.4'te CAN hattı çözülemezse, ya da Faz 5 öncesi bağımsız
doğrulama için. **Alınırsa CY7C68013A / FX2LP çipli olmalı** — kurulu
`sigrok-firmware-fx2lafw` ve PulseView yalnızca bunları tanır.

| Satıcı | Fiyat | Stok |
|---|---|---|
| Amazon.com.tr (SeenGreat, CY7C68013A, sigrok uyumlu) | — | ✅ |
| Robiz.net | 518,40 TL | ⚠️ 10-15 gün |
| Robotistan | 461,84 TL | ❌ Tükendi |
| Direnç.net | 418,45 TL | ❌ Tükendi |

---

## Bütçe özeti

| | Tutar |
|---|---|
| İlk sipariş (Robiz, tek kargo) | **656,16 TL** |
| 120 Ω direnç (gerekirse, yerel) | ~10 TL |
| Mantık analizörü (ertelendi) | ~420–520 TL |

Proje önerisindeki "~250 TL" tahmini yalnızca CAN modüllerini kapsıyordu. Kablolar,
dönüştürücü, breadboard ve veri kablosu eklenince ilk sipariş bu seviyeye çıkıyor.
Hocana bütçe söylerken bu rakamı kullan.
