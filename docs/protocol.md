# Haberleşme Protokolü

> Kart ile bilgisayar arasındaki mesajların **neden böyle tasarlandığını** anlatır.
> Mesajların kendisi tek bir yerde tanımlıdır: **`shared/protocol/messages.yaml`** (K-003).
> Kuralların ve eşiklerin anlamı: `docs/RULES.md` · Kararlar: `docs/DECISIONS.md` K-014.

**Son güncelleme:** 2026-09-24 · **Şema sürümü:** 1

```bash
python3 tools/gen_protocol.py              # messages.yaml → C, Python, test vektörleri
python3 tools/gen_protocol.py --check      # üretilenler güncel mi
python3 -m pytest shared/protocol/tests    # 80 test, C↔Python bayt eşitliği dahil
```

| Dosya | Ne | Kim yazar |
|---|---|---|
| `shared/protocol/messages.yaml` | Mesajların **tek** tanımı | elle |
| `shared/protocol/c/proto_msgs.h` | C yapıları, kodlayıcı/çözücüler | **üretilir** |
| `shared/protocol/python/ika_protocol/messages.py` | Python sınıfları | **üretilir** |
| `shared/protocol/test_vectors.json` | Faz 2'deki C çerçeveleyicisinin tutturacağı baytlar | **üretilir** |
| `shared/protocol/python/ika_protocol/frame.py` | Çerçeveleme (COBS, CRC, HMAC): referans uygulama | elle |
| `tools/gen_protocol.py` | Üretici ve şema doğrulayıcı | elle |

---

## 1. Genel bakış

```
                    AJAN KANALI                          ARAÇ KANALI
                 (USB → Nucleo VCP)                  (USART → CP2102 → USB)
┌────────────┐                     ┌─────────────────────────┐                     ┌────────────┐
│  Köprü     │── HEARTBEAT ──────▶ │ Bekçi       CAN      Araç│ ◀── TELEMETRY ──────│  Köprü     │
│ (ajan      │── VELOCITY_CMD ───▶ │ tarafı  ═════════▶  tarafı│── DRIVE ──────────▶ │ (araç      │
│  tarafı)   │── GOTO/WAIT/... ──▶ │ FDCAN1  ◀═════════  FDCAN2│── GOAL ───────────▶ │  tarafı)   │
│            │── RESET_CMD ──────▶ │                          │── HALT ───────────▶ │            │
│            │◀── HEARTBEAT_ACK ── │                          │── SPEED_LIMIT_SET ▶ │  → Nav2    │
│            │◀── VERDICT ──────── │                          │                     │  → İKA     │
│            │◀── STATUS, HELLO ── │                          │── STATUS, HELLO ──▶ │            │
└────────────┘                     └─────────────────────────┘                     └────────────┘
```

17 mesaj var. Tam liste, alanlar ve birimler için `messages.yaml`.

| Grup | Mesajlar |
|---|---|
| Oturum ve bağlantı | `HELLO_REQ`, `HELLO`, `HEARTBEAT`, `HEARTBEAT_ACK`, `STATUS` |
| Ajan → kart | `VELOCITY_CMD` (Nav2, 20 Hz) · `GOTO_CMD`, `WAIT_CMD`, `SPEED_LIMIT_CMD`, `STOP_CMD` (LLM) · `RESET_CMD` |
| Kart → ajan | `VERDICT` (karar ve gerekçe) |
| Araç → kart | `TELEMETRY` |
| Kart → araç | `HALT`, `DRIVE`, `GOAL`, `SPEED_LIMIT_SET`: hepsi CAN'den geçer |

---

## 2. Tehdit modeli: HMAC neyi yakalar, neyi yakalamaz

Bu ayrım tezde net durmalı. Yoksa "HMAC var, sistem güvenli" gibi yanlış bir çıkarıma
açık kalınır.

| Tehdit | Kim yakalar |
|---|---|
| **LLM'in hatalı ya da kötü niyetli komutu** (uydurma hedef, aşırı hız, prompt injection) | **İçerik kuralları** (GEOFENCE, LIMIT, CONSISTENCY). **HMAC yakalamaz**: komut meşru boru hattından geçer ve köprü tarafından imzalanır. |
| **Kanala dışarıdan enjeksiyon**: anahtarı olmayan bir süreç ya da cihaz seri porta yazar | **AUTH** (demodaki "sahte komut") |
| **Tekrar**: yakalanmış geçerli bir çerçeve yeniden gönderilir | **REPLAY** |
| **Eski oturumun çerçevesi**: kart yeniden başladıktan sonra | **AUTH**: oturum kimliği imzaya girer (§5) |
| **Ajan tarafının sahte telemetri üretmesi** | **Porta göre güven**: `TELEMETRY` yalnızca araç kanalının fiziksel portundan kabul edilir. Kriptografiye gerek kalmadan fiziksel ayrım. |
| **Kartın kendi çerçevesinin ona geri yansıtılması** | **Yön denetimi**: yön kimliğin en üst bitinde (§4.6) |

**Güvenilir kabul edilen:** araç tarafı. Gerçek bir araçta bu, araç içi veri yoludur.
Simülasyonda araç tarafının da aynı PC'de çalışması bir **düzenek kısıtıdır** ve tezde
böyle belirtilmelidir.

**Kapsam dışı:** PC'nin anahtarla birlikte tamamen ele geçirilmesi. Önemli olan, **bu
durumda bile kartın içerik kuralları, fiziksel limitleri ve kalp atışı çalışmaya devam
eder.** HMAC bir katmandır, güvenliğin temeli değildir. Temel, basit ve bağımsız
denetleyicidir (Simplex).

**Karta fiziksel erişim de kapsam dışı.** Anahtar kartın flash'ında durur ve okuma koruması
(RDP) açık değildir: kartın ST-LINK'ine bağlanan biri anahtarı okuyabilir. Gerçek bir
araçta okuma koruması açılır ve hata ayıklama bağlantısı kapatılır. Bu düzenekte kart her
yüklemede ST-LINK'le programlandığı için açılmadı.

**Protokolle gönderilmeyenler:** coğrafi sınır çokgenleri, güvenli noktalar ve eşikler.
Bunlar derleme zamanında karta gömülür. Güvenilmeyen tarafın bunları değiştirebilmesi
denetimin anlamını ortadan kaldırırdı.

**CAN hattında HMAC yok.** Araç içi veri yolu güvenilir tarafta kalıyor. Gerçek araçlarda
bunun karşılığı AUTOSAR SecOC gibi mekanizmalardır, bu projenin kapsamı dışındadır.

---

## 3. Veri gösterimi: neden hiç kayan nokta yok

Hattaki tüm sayılar **little-endian tamsayıdır** (Cortex-M4 ve x86'nın doğal sırası).

| Büyüklük | Birim | Tip | Aralık | Çözünürlük |
|---|---|---|---|---|
| Konum | cm | int16 | ±327,67 m | 1 cm |
| Açı | mrad | int16 | ±32,767 rad ([-π, π]'ye normalize) | 0,001 rad |
| Doğrusal hız | mm/s | int16 | ±32,767 m/s | 1 mm/s |
| Açısal hız | mrad/s | int16 | ±32,767 rad/s | 0,001 rad/s |
| Zaman | ms | uint32 | 49,7 gün, sonra taşar | 1 ms |

**En önemli gerekçe güvenlik:** kayan noktada `NaN` vardır ve `NaN > 0,30` **yanlış** döner.
`v = NaN` taşıyan bir hız komutu, "0,30'dan büyük mü?" denetiminden sessizce geçer. Tamsayıda
böyle bir değer yoktur.

Diğer gerekçeler: bayt düzeni tanımsızlığı yok, karşılaştırmalar belirlenimci, CAN'in
8 baytına sığıyor (`GOAL`: x, y, yön, kaynak = 7 bayt).

Aralıklar gereğin çok üstünde. Bekçinin 300 mm/s limiti int16'nın %1'i bile değil.
Simülasyon ortamı da ±327 m'nin çok içinde.

---

## 4. Çerçeve

### 4.1 Yapı

```
COBS( başlık ‖ yük ‖ etiket ‖ CRC ) ‖ 0x00
```

| Alan | Bayt | İçerik |
|---|---|---|
| `type` | 1 | Mesaj kimliği. Üst bit yönü gösterir (§4.6) |
| `seq` | 4 | Gönderenin kesin artan sayacı |
| `ts_ms` | 4 | Gönderim anı, **her zaman kartın saat alanında** (§6) |
| yük | 0–23 | Mesaja göre sabit uzunluk |
| etiket | 8 | HMAC-SHA256'nın ilk 8 baytı. İmzasız `HELLO_REQ`'te sıfır |
| CRC | 2 | CRC-16/CCITT-FALSE, önceki her şeyin üstünde |
| ayraç | 1 | `0x00` |

**Uzunluk alanı yok.** Yük uzunluğu tipe göre sabit ve **tam eşitlik** denetleniyor.
Uzunluk alanı olsaydı, bozulduğunda alıcının ne kadar okuyacağını şaşırtırdı.

En uzun çerçeve (`VERDICT`) hatta **44 bayt**. Alıcı tamponu 64 bayt.

### 4.2 Neden başlangıç baytı değil COBS

Plan "başlangıç baytı" diyordu (ör. her çerçeve `0xAA` ile başlar). Bunun iki sorunu var:

1. **Yükte de `0xAA` geçebilir.** Senkron kaybolduğunda alıcı yükün ortasındaki `0xAA`'yı
   çerçeve başı sanır. CRC tutmaz, çerçeve "bozuk" sayılır ama aslında hat bozuk değildir.
2. **Bozulmuş bir uzunluk alanı**, arkasından gelen geçerli çerçeveleri de yutar.

Plan "bozuk çerçeve sessizce atılmaz, **sayılır ve raporlanır**" diyor. Bu iki sorun o
sayımı yanlış çıkarır: hat gürültüsü olduğundan fazla görünür.

**COBS** (Consistent Overhead Byte Stuffing) veriyi, içinde hiç `0x00` kalmayacak şekilde
yeniden kodlar. Böylece `0x00` **yalnızca** çerçeve sonunda görünür:

- Senkron **tek baytta** geri gelir: bir sonraki `0x00`'dan itibaren her şey temizdir.
- Sayım kesindir: bir bozulma tam olarak bir çerçeveyi etkiler.
- Maliyeti **en fazla 254 baytta 1 bayt**. Bizim çerçevelerimizde her zaman tam 1 bayt.

Başlangıç baytının amacı çerçeve sınırını bulmaktı. COBS bu amacı daha güvenilir biçimde
karşılıyor.

### 4.3 Neden hem CRC hem HMAC

İkisi farklı sorulara cevap veriyor:

| | CRC | HMAC |
|---|---|---|
| Soru | "Hat bu baytları bozdu mu?" | "Bunu anahtarı bilen biri mi gönderdi?" |
| Maliyet | Çok ucuz | Onlarca µs (Faz 2.6'da ölçülecek) |
| Sayaç | `err_crc`: **hat kalitesi** | `err_auth`: **yakalanan saldırı** |

**Gürültü ile saldırıyı ayırt etmek S1 için şart.** Tek bir "geçersiz çerçeve" sayacı
olsaydı, gürültülü bir kablo yakalanmış saldırı gibi görünürdü. CRC önce gelir: çöp veri
üzerinde HMAC hesaplanmaz.

### 4.4 Bayt düzeyinde örnek

`VELOCITY_CMD` (v = 250 mm/s, ω = −500 mrad/s), seq = 1, ts = 1000 ms, **test anahtarıyla**:

| Alan | Değer | Bayt |
|---|---|---|
| `type` | 0x10 | `10` |
| `seq` | 1 | `01 00 00 00` |
| `ts_ms` | 1000 | `E8 03 00 00` |
| `v_mm_s` | 250 | `FA 00` |
| `w_mrad_s` | −500 | `0C FE` |
| etiket | HMAC | `06 1A 85 7A 51 0A AA 4E` |
| CRC | | `7F 18` |

23 bayt ham çerçeve, COBS ile **25 bayt** oluyor:

```
03 10 01 01 01 03 E8 03 01 02 FA 0D 0C FE 06 1A 85 7A 51 0A AA 4E 7F 18 00
```

Ham verideki altı `0x00` (sayaçta üç, zaman damgasında iki, yükte bir) kayboldu. Her
bloğun başına "bir sonraki sıfıra kadar kaç bayt var" kodu geldi:
`03 01 01 03 01 02 0D`. Hattaki tek `0x00` en sondaki ayraç.

### 4.5 Neden 8 baytlık etiket

HMAC-SHA256 32 bayt üretir. İlk 8'i (64 bit) kullanılıyor.

**Kaba kuvvetle tahmin:** 115200 baud'da hat saniyede en fazla ~460 kısa çerçeve taşır.
2⁶⁴ olası etiketi denemek **yaklaşık 1,3 milyar yıl** sürer. Hat hızı saldırganın
önündeki doğal sınırdır.

**Tam etiketin bedeli:** her çerçeveye 24 bayt daha eklenirdi. `VELOCITY_CMD` 25 bayttan
49 bayta çıkar, 20 Hz'lik hız akışının hattaki süresi iki katına çıkardı. Kısaltılmış MAC,
düşük bant genişlikli gömülü hatlarda yaygın bir uygulamadır (otomotivde SecOC da
kısaltılmış MAC kullanır).

**Faz 2 notu:** C tarafında etiket **sabit zamanlı** karşılaştırılmalı (`memcmp` değil).
Aksi hâlde yanıt süresinden etiketin kaç baytının doğru olduğu sızabilir. Python tarafı
`hmac.compare_digest` kullanıyor.

### 4.6 Tip, yön, kanal, uzunluk

`err_type` tek sayaçta dört şeyi yakalar:

- **Bilinmeyen tip.**
- **Yanlış yön.** Bilgisayardan karta giden kimlikler `< 0x80`, karttan gidenler `≥ 0x80`.
  Kartın kendi gönderdiği bir çerçeve ona geri yansıtılırsa tek bir bit testiyle düşer.
  Üretici bu kuralı zorluyor.
- **Yanlış kanal.** Her mesaj bir porta aittir. `TELEMETRY` ajan portundan gelirse reddedilir.
- **Yanlış uzunluk.**

### 4.7 Alıcı denetim sırası

`docs/RULES.md` §4 ile aynı sıra. Her adımın kendi `STATUS` sayacı var:

| # | Denetim | Sayaç | VERDICT? |
|---|---|---|---|
| 1 | Tampon taşması, COBS | `err_framing` | hayır |
| 2 | CRC | `err_crc` | hayır |
| 3 | Tip, yön, kanal, uzunluk | `err_type` | hayır |
| 4 | HMAC (`HELLO_REQ` hariç) | `err_auth` | hayır |
| 5 | Sayaç | `err_replay` | hayır |
| 6 | Tazelik | `err_fresh` | görev komutunda evet |
| 7 | Mod, içerik kuralları | — | görev komutunda evet |

**1–5. adımlarda karttan hiçbir çıktı üretilmez**, yalnızca sayaç artar. İmzasız girdinin
karttan cevap tetiklemesi iki açık yaratırdı: saldırgana bilgi sızar ve kart, bir göndericinin
yukarı yönü boğması için araca dönüşür.

---

## 5. Oturum

### 5.1 Sorun

Tekrar kuralı "sayaç son kabul edilenden büyük mü" diye bakar. Ama **kart yeniden
başladığında son kabul edilen sayaç sıfırlanır.** Önceki oturumdan kaydedilmiş, sayacı
büyük herhangi bir çerçeve yeniden kabul edilir.

Sayacı flash belleğe yazmak bir çözüm olabilir ama yazma ömrü ve karmaşıklık getirir.

### 5.2 Çözüm: oturum kimliği imzaya girer

Kart açılışta **donanım rastgele sayı üretecinden** (STM32G4'ün RNG birimi) 32 bitlik bir
`session_id` üretir. Bu kimlik her çerçevenin HMAC girdisine eklenir ama çerçevede taşınmaz:

```
etiket = HMAC-SHA256(anahtar, session_id ‖ başlık ‖ yük)[0:8]
```

Önceki oturumun her çerçevesi farklı bir `session_id` ile imzalanmıştır, dolayısıyla
**AUTH ile düşer.** Sayaç her oturumda sıfırdan başlayabilir.

Oturum kimliği gizli değildir, `HELLO` içinde açıkça duyurulur. Güvenlik anahtardan gelir.
Kimliğin tek görevi, oturumları birbirinden ayırmaktır.

### 5.3 Akış

```
Kart açılır
  ├─ Durum: HOLD (docs/RULES.md §5.2)
  ├─ session_id = RNG()
  └─ Her iki kanaldan 500 ms'de bir HELLO yayınla
         │
Köprü HELLO'yu alır
  ├─ Etiketi, HELLO'nun içindeki session_id ile doğrular
  ├─ schema_hash kendi özetiyle eşleşmiyor mu? → DUR, hata ver (§5.4)
  ├─ Sayacına last_rx_seq + 1'den başlar
  ├─ Saat farkının ilk tahmini: HELLO başlığındaki ts_ms (§6)
  └─ HEARTBEAT'e başlar (100 ms)
         │
Kart ilk geçerli çerçeveyi alır → HELLO yayınını keser
         │
Deney betiği ya da operatör RESET_CMD gönderir → NORMAL
```

**Köprü yeniden başlarsa** `HELLO_REQ` gönderir. Kart, içinde güncel `last_rx_seq` olan
`HELLO` ile cevap verir ve köprü kaldığı yerden devam eder. **Kartın durumu değişmez.**

`HELLO_REQ` imzasızdır, çünkü köprü oturum kimliğini henüz bilmiyor olabilir. Kartın
durumunu değiştirmez ve cevabı saniyede 2 ile sınırlıdır. Bu yüzden "durumu yalnızca
imzalı mesajlar değiştirir" ilkesiyle çelişmez.

Her kanalın kendi sayaç alanı vardır. Oturum kimliği ortaktır.

### 5.4 Şema özeti: tek kaynak ilkesinin çalışma zamanı denetimi

`HELLO`, `messages.yaml`'ın 32 bitlik özetini taşır (şu an `0xB12F26D8`). Özet yalnızca
anlamı değiştiren düzenlemelerde değişir, `doc:` satırlarındaki düzenlemeler onu etkilemez.

Köprünün özeti karttakinden farklıysa köprü **çalışmayı reddeder.** K-003'ün önlemek
istediği hata tam olarak budur: kart eski bir `messages.yaml` ile derlenmiş, köprü yenisiyle
çalışıyor. İki taraf farklı baytlar bekler. Bu hata sessiz kalmaz, ilk bağlantıda açıkça
görünür.

---

## 6. Zaman eşitleme

### 6.1 Neden gerekli

Tazelik ve tutarlılık kuralları süreleri **kartın saatine** göre ölçer. Ama kartın ve
bilgisayarın saatleri bağımsız çalışır ve birbirinden kayar:

| Kart saat kaynağı | Hassasiyet | Bir saatte kayma |
|---|---|---|
| Dahili RC osilatör (HSI) | ±%1 | **~36 s** |
| Harici kristal (HSE) | ~±50 ppm | ~0,2 s |

İkisinde de açılışta bir kez eşitlemek yetmez: 200 ms'lik tazelik eşiği birkaç dakika
içinde anlamsızlaşır. Bu yüzden eşitleme sürekli yapılır (§6.2). Saniyede 10 örnekle
kayma iki kaynakta da birikmez, yani **zaman eşitlemesi HSE'yi gerektirmez.**

Kartta yine de HSE kullanılıyor (Faz 2.1), ama sebebi başka: DWT çevrim sayacıyla
ölçülen karar süreleri, saatin tam 170 MHz olduğu varsayımıyla mikrosaniyeye çevrilir.
HSI'nın ±%1 toleransı, S1'de raporlanan her gecikmeye ±%1'lik sistematik bir hata
ekler. Kristalde bu hata ihmal edilebilir.

### 6.2 Yöntem: her kalp atışı bir eşitleme örneği

NTP'nin basitleştirilmiş hali. Ek bir mesaj gerekmiyor:

```
t₀  Köprü:  HEARTBEAT(echo_pc_ms = t₀)              ──▶
    Kart:   HEARTBEAT_ACK(echo_pc_ms = t₀),
            başlıkta ts_ms = kartın saati (T)        ◀──
t₁  Köprü:  alır

    RTT   = t₁ − t₀
    fark  = T − (t₀ + t₁) / 2
    kart_saati ≈ pc_saati + fark
```

Köprü son 10 örnekten **RTT'si en küçük olanı** kullanır. Gecikmesi en az olan örnek en az
belirsiz olandır. Hata en fazla RTT/2'dir. USB sanal seri portta RTT birkaç ms olduğundan
hata da birkaç ms, 200 ms'lik eşiğin yanında önemsiz. Örnekler saniyede 10 kez yenilendiği
için kayma hiç birikmez.

### 6.3 Kural: `ts_ms` her zaman kartın saat alanındadır

- **Kartın gönderdiği çerçevelerde** doğrudan kartın saatidir.
- **Bilgisayarın gönderdiklerinde** köprünün tahminidir.
- **Dönüşümün tek sorumlusu köprüdür.** Ajan konumu okuduğu anı ROS zamanıyla verir.
  Köprü bunu `belief_ts_ms` alanına yazmadan önce kartın saat alanına çevirir.

### 6.4 Gelecekten gelen zaman damgası

Komutun zaman damgası kartın saatinden **50 ms'den fazla ilerideyse**, komut
`FRESHNESS / FROM_FUTURE` ile reddedilir. 50 ms, eşitleme hatasına tanınan paydır. Bundan
büyük bir fark eşitlemenin bozulduğunu gösterir. Böyle bir durumda komut kabul edilseydi
tazelik denetimi fiilen devre dışı kalırdı. Kabul edilen aralık: **−50 ms ≤ yaş ≤ 200 ms.**

---

## 7. Karar ve gerekçe (`VERDICT`)

### 7.1 Biçim

Planın istediği üç şey, "hangi kural, neden, izinli değer aralığı", şu alanlarla karşılanır:

| Alan | Anlam |
|---|---|
| `ref_seq` | Karar verilen çerçevenin sayacı. Ajan kararı kendi komutuyla eşleştirir |
| `result` | `ACCEPTED` / `REJECTED` |
| `rule` | Hangi kural |
| `reason` | Neden. Diğer alanların anlamını belirler |
| `value` | Ölçülen değer |
| `lo`, `hi` | İzinli aralık |
| `hint_x_cm`, `hint_y_cm` | İpucu noktası |

| `reason` | `value` | `lo` / `hi` | ipucu |
|---|---|---|---|
| `TOO_OLD` | komut yaşı (ms) | — / 200 | — |
| `FROM_FUTURE` | yaş (ms, negatif) | −50 / — | — |
| `IN_RECOVERY`, `IN_HOLD`, `NOT_IN_HOLD` | — | — | — |
| `GOAL_OUTSIDE_ALLOWED`, `GOAL_IN_FORBIDDEN` | — | — | **en yakın kayıtlı güvenli nokta** |
| `ABOVE_MAX`, `NOT_POSITIVE` | istenen (mm/s) | 1 / 300 | — |
| `TOO_FAR` | fark (cm) | — / tolerans (cm) | **aracın gerçek konumu** |
| `BELIEF_TOO_OLD` | Δt (ms) | — / 10000 | — |
| `BELIEF_FROM_FUTURE` | Δt (ms, negatif) | −50 / — | — |
| `NO_TELEMETRY` | telemetri yaşı (ms) | — / 500 | — |

**İpuçları S3 için seçildi.** Tutarlılık reddinde ajana aracın gerçek konumu söylenir,
coğrafi sınır reddinde gidebileceği güvenli bir nokta. D yapılandırmasındaki ajanın tek
denemede düzeltebilmesi için gereken bilgi tam olarak bu.

### 7.2 Kim `VERDICT` alır

- **İmzası doğrulanmış, tekrar olmayan her görev komutu ve `RESET_CMD`.** Hem kabulde hem
  retde. Ajan komutunun kabul edildiğini de bilmeli.
- **`VELOCITY_CMD` almaz.** 20 Hz'de her komuta cevap yukarı yönü boğardı. Kırpmalar
  `STATUS.clipped` sayacında görünür.
- **1–5. adımlarda düşen hiçbir çerçeve almaz** (§4.7).

### 7.3 C ve D yapılandırmaları: fark köprüde

**Kart her yapılandırmada tam gerekçeyi gönderir.** C yapılandırmasında köprü, ajana
yalnızca "komut reddedildi" iletir ve gerekçeyi gizler.

Bunun iki sebebi var:

1. **Kart iki yapılandırmada birebir aynı.** Deneydeki tek değişken ajanın gördüğü metin.
   Farklı bir firmware kullanılsaydı "sonuç farkı gerekçeden mi, firmware farkından mı?"
   sorusu doğardı.
2. **S1 kayıtları C'de de tam.** Hangi kuralın neyi yakaladığı her yapılandırmada ölçülür.

`VERDICT`'i ajanın anlayacağı metne çevirmek köprünün ve ajanın işi (Faz 4). Örnek:

> Komut reddedildi (CONSISTENCY / TOO_FAR). Varsaydığın konum telemetriden 3,10 m uzak,
> tolerans 1,45 m. Aracın şu anki konumu: (4,20 ; 1,50).

---

## 8. CAN eşlemesi

Onaylı komutlar bekçi tarafından (FDCAN1) araç tarafına (FDCAN2) CAN üzerinden geçer.
Telemetri ters yönde geçer. Bu, K-002'deki tek kartlı HIL düzeneğinin veri yolu kısmı.

| Mesaj | CAN ID | Yük | Yön |
|---|---|---|---|
| `HALT` | **0x100** | 2 bayt | bekçi → araç |
| `DRIVE` | 0x110 | 4 bayt | bekçi → araç |
| `GOAL` | 0x120 | 7 bayt | bekçi → araç |
| `SPEED_LIMIT_SET` | 0x130 | 2 bayt | bekçi → araç |
| `TELEMETRY` | 0x200 | 6 bayt | araç → bekçi |

- **Klasik CAN, 500 kbit/s** (plan), yük ≤ 8 bayt. Üretici bunu zorluyor.
- **CAN yükü, `messages.yaml`'daki yükün aynısı.** Ek başlık yok. CAN'in kendi CRC'si var,
  HMAC yok (§2).
- **Kimlikler öncelik sırasında.** CAN'de iki düğüm aynı anda gönderirse küçük kimlik
  kazanır. `HALT` en küçük kimliğe sahip: **durdurma komutu hiçbir zaman bir hız ya da
  hedef mesajının arkasında beklemez.** Telemetri en düşük öncelikte.
- **Araç tarafı düğümü** CAN'den aldığı yükü seri çerçeveye sarar (sayaç, zaman damgası,
  etiket, CRC) ve araç kanalından gönderir. Telemetri için tersini yapar.

---

## 9. Bant genişliği ve gecikme

115200 baud ≈ 11 520 bayt/s.

| Hat | Akış | Yük |
|---|---|---|
| Ajan, PC → kart | `VELOCITY_CMD` 25 B × 20 Hz + `HEARTBEAT` 25 B × 10 Hz | ~750 B/s · **%6,5** |
| Ajan, kart → PC | `HEARTBEAT_ACK` 27 B × 10 Hz + `STATUS` 41 B × 1 Hz | ~310 B/s · **%2,7** |
| Araç, PC → kart | `TELEMETRY` 27 B × 20 Hz | ~540 B/s · **%4,7** |
| Araç, kart → PC | `DRIVE` 25 B × 20 Hz + `STATUS` | ~540 B/s · **%4,7** |

Hatlar %7'nin altında dolu, görev komutları ve `VERDICT`'ler için bol pay var.

**Gecikme:** bir çerçevenin hatta geçirdiği süre `VELOCITY_CMD` için 2,2 ms, en uzun
çerçeve için 3,8 ms. Bu, S1'in uçtan uca gecikmesinin bir bileşeni. Gerekirse ST-LINK'in
sanal seri portu daha yüksek hızları destekler. Karar Faz 2'de ölçümle verilecek.

---

## 10. Köprünün sorumlulukları (Faz 3 için özet)

Köprü, protokolün bilgisayar tarafındaki tek uygulayıcısıdır:

- `HELLO` / `HELLO_REQ` ile oturum kurmak, `schema_hash` denetimi (§5)
- Her çerçeveyi imzalamak (anahtar köprüde durur), sayacı yönetmek
- `HEARTBEAT`'i 100 ms'de bir göndermek, saat farkını tahmin etmek (§6)
- Tüm zaman damgalarını kartın saat alanına çevirmek, `belief_ts_ms` dahil
- `TELEMETRY`'yi 20 Hz'de araç kanalından göndermek
- Araç kanalından gelen `GOAL`, `DRIVE`, `HALT`, `SPEED_LIMIT_SET`'i ROS'a iletmek
- `VERDICT`'i ajana iletmek. **C yapılandırmasında gerekçeyi gizlemek** (§7.3)
- `STATUS` sayaçlarını deney kaydına yazmak

---

## 11. Anahtar

- 32 bayt rastgele. `secrets/hmac_key.bin` dosyasında durur, **depoya girmez** (K-007,
  `.gitignore`).
- Anahtar ve kartın başlığı `tools/gen_key.py` ile üretilir: `secrets/hmac_key.bin` yoksa
  `os.urandom` ile oluşturulur, varsa **üzerine yazılmaz**. `secrets/hmac_key.h` her
  çalıştırmada .bin'den yeniden yazılır. CubeIDE derlerken betik çalıştırmadığı için
  başlık derlemeden önce üretilir. Kart anahtarı `firmware/app/auth/key` üzerinden alır.
  Başlık yoksa derleme durur.
- **Parmak izi:** `HMAC(anahtar, "IKA anahtar denetimi")`'nin ilk 8 baytı. İki tarafın aynı
  anahtarı bildiği, anahtar gösterilmeden bununla denetlenir. Gizli değildir.
- Anahtar değiştirilirse kart yeniden derlenip yüklenmeli. Aksi hâlde her çerçeve
  `err_auth` ile reddedilir.
- `test_vectors.json`'daki anahtar (`00 01 02 … 1F`) **yalnızca test içindir**, gerçek
  anahtar olarak kullanılmaz.

---

## 12. Değişiklik süreci

1. `shared/protocol/messages.yaml`'ı düzenle
2. `python3 tools/gen_protocol.py`
3. `python3 -m pytest shared/protocol/tests`
4. YAML'ı ve üretilen üç dosyayı **aynı commit'te** gönder

Üretici, dosyayı yazmadan önce şemayı doğrular. Tekrarlanan kimlik, CAN'e sığmayan yük,
tampona sığmayan çerçeve, yanlış yön biti ya da tipine sığmayan enum değeri varsa hiçbir
şey yazmadan durur.

---

## 13. Açık kalanlar

| Konu | Ne zaman |
|---|---|
| ~~C çerçeveleyici: COBS, CRC, HMAC-SHA256. `test_vectors.json`'a karşı doğrulanacak~~ ✅ `firmware/app/protocol/`, `firmware/app/auth/` (K-021) | Faz 2.6 |
| ~~Etiketin sabit zamanlı karşılaştırılması (§4.5)~~ ✅ `hmac_tag_equal()`. Süre ölçümü kartta | Faz 2.6 |
| ~~HMAC'in karttaki süresi (DWT ile)~~ ✅ `-Os`'ta 142 µs, karşılaştırma sabit zamanlı (K-022) | Faz 2.6 |
| Baud hızının ölçümle kesinleşmesi | Faz 2 |
| A yapılandırmasında köprünün kartı nasıl atlayacağı | Faz 5 |
