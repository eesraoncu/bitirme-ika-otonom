# Kurallar, Eşik Değerleri ve Kurtarma

> Bekçi kartının **neyi, hangi eşikle denetlediğinin** ve **ihlalde ne yaptığının** tek
> başvuru belgesi. Mesajların biçimi burada değil, `docs/protocol.md`'de.
> Kararların gerekçe geçmişi: `docs/DECISIONS.md` K-010 … K-014. Protokol: `docs/protocol.md`.
> Tüm değerler onaylandı (2026-09-24).

**Son güncelleme:** 2026-10-08 (§1 İKA'ya göre yeniden kuruldu, K-039)

---

## 1. Katmanlı limitler

Bekçinin limiti **Nav2'nin kendi ayarının üstünde, platformun tavanının altında** durur (K-012).

| | Nav2 (`ika_nav`) | **Bekçi** | İKA tavanı |
|---|---|---|---|
| Doğrusal hız | 0,5 m/s | **0,6 m/s** | 3,6 m/s (13 km/h) |
| Açısal hız | 0,5 rad/s | **0,6 rad/s** | ~7 rad/s (hesap) |
| Doğrusal ivme (hızlanma) | 0,5 m/s² | **0,6 m/s²** | bilinmiyor |
| Açısal ivme (hızlanma) | 1,0 rad/s² | **1,2 rad/s²** | bilinmiyor |

- **Nav2'nin üstünde, çünkü** normal çalışmada Nav2'nin ürettiği komutların hiçbiri
  kırpılmamalı. Aksi hâlde her komut "ihlal" sayılır ve yanlış alarm oranı (S1'in ikinci
  yarısı) anlamsızlaşır.
- **Platformun altında, çünkü** platform tavanında duran bir limit hiç tetiklenmez.
  Araç o hızı fiziksel olarak aşamaz. "Sınırları zorlayan talimatlar" senaryosunun
  (Faz 5) veri üretebilmesi için bekçinin bir yerde *hayır* diyebilmesi gerekir.
- Bekçi değerleri Nav2'nin **1,2 katı**. İKA tavanın çok altında: araç 3,6 m/s
  gidebilir, bekçi saha güvenliği için 0,6'da keser.
- **İvme Nav2'de yumuşatıcıyla sınırlı, bekçide yalnız hızlanma denetlenir (K-046):**
  Nav2'nin denetleyicisi (Regulated Pure Pursuit) doğrusal ivmeyi sınırlamıyor: 2026-10-14
  ölçümünde kalkışta 0 → 0,5 m/s tek adımda (10 m/s²), 1,2 kat kuralı anlamsız sınır verirdi.
  Nav2'ye `velocity_smoother` eklendi: hızlanma 0,5 m/s² · 1,0 rad/s², yavaşlama sınırsız.
  Ölçüm (`tools/nav2_accel_bench.py`, 5 150 komut): hızlanma adımı en çok 0,025 m/s, bekçinin
  sınırını aşan komut 0. Yavaşlama neden kırpılmaz: §3.2.
- **Açısal hız doğrulandı (2026-10-14):** Nav2'nin 0,5 rad/s'si yalnız yerinde dönüş ve
  kurtarmanın sınırı; yol takibinde Pure Pursuit `ω = v × eğrilik` üretir. Ölçülen en çok
  0,556 rad/s (4 bacaklı tur, 4 415 hareket komutu), 0,6'yı aşan yok. Sınır değişmedi.

**Kaynaklar:**
- Nav2: `ros2_ws/src/ika_nav/config/nav2_params.yaml` (`desired_linear_vel`,
  `rotate_to_heading_angular_vel`, behavior `max_rotational_vel`, velocity_smoother
  `max_accel`).
- İKA doğrusal tavanı: Orinium UGV ÇGM, TEKNOFEST 2026 Kritik Tasarım Raporu, §3.1.4
  Tablo-3 "Maksimum Hız 13 km/h". Aynı raporun Şekil 11'inde 15 km/h (düz yol) ve 30 km/h
  da geçiyor; resmî özellik tablosu esas alındı. Sağlama: 2850 rpm, 12:1 redüksiyonla
  13 km/h için ~29 cm palet dişlisi gerekir; makul.
- İKA açısal tavanı: diferansiyel sürüşte ω = 2·v / iz. İz = 1200 − 180 mm (genişlik −
  palet eni) ≈ 1,02 m (modelde 1,026). 2 × 3,6 / 1,02 ≈ 7 rad/s. Teorik üst sınır; paletin
  yanal kayması gerçek değeri düşürür.

---

## 2. Kural tablosu

İki tür komut vardır: **görev komutu** (LLM ajanından, seyrek: `git`, `bekle`,
`hiz_siniri`, `dur`) ve **hız komutu** (Nav2'den, 20 Hz, `cmd_vel`).

| Kural | Kod | Uygulandığı | Eşik | İhlalde | Gerekçede dönen |
|---|---|---|---|---|---|
| Coğrafi sınır: hedef | `GEOFENCE` | görev (`git`) | izinli çokgen içinde, yasak çokgenlerin dışında | **Ret** | reddedilen hedef, en yakın kayıtlı güvenli nokta |
| Coğrafi sınır: araç konumu | `GEOFENCE` | telemetri | aynı | **Kurtarma** (§5) | — |
| Fiziksel limit: görev | `LIMIT` | görev (`hiz_siniri`) | 0 < değer ≤ 0,60 m/s | **Ret** | istenen değer, izinli aralık |
| Fiziksel limit: hız | `LIMIT` | hız | \|v\| ≤ 0,60 · \|ω\| ≤ 0,6 · Δv, Δω sınırlı (§3.2) | **Kırp** | — (kayda geçer) |
| Tazelik | `FRESHNESS` | her ikisi | **−50 ms ≤ yaş ≤ 200 ms** | **Ret** | komut yaşı, izinli aralık |
| Kimlik | `AUTH` | her ikisi | HMAC etiketi doğru | **Sessiz ret** | gönderilmez, `STATUS` sayacı |
| Tekrar | `REPLAY` | her ikisi | sayaç > son kabul edilen | **Sessiz ret** | gönderilmez, `STATUS` sayacı |
| Tutarlılık | `CONSISTENCY` | görev | konum farkı ≤ tol(Δt) (§3.4) | **Ret + uyarı** | varsayılan konum, telemetri konumu, fark, tolerans |
| Kalp atışı | `HEARTBEAT` | bağlantı | son kalp atışından ≤ **500 ms** | **Kurtarma** (§5) | — |
| Mod | `MODE` | görev | kart `NORMAL` durumda | **Ret** | kartın mevcut durumu |

**Görev komutunda limit aşımı reddedilir, hız komutunda kırpılır.** Ayrımın sebebi:
`hiz_siniri(0,4)` LLM'in niyetini gösterir. Reddedilirse S1'de "yakalandı" sayılır ve
D yapılandırmasında ajan gerekçeyi görüp düzeltebilir (S3). Nav2'nin hız komutu ise
bir kontrol döngüsünün çıktısıdır. Reddedilirse araç sarsılır, kırpmak yeterli ve
güvenlidir. Kırpma olayları yine de kaydedilir (`STATUS.clipped`).

**`dur()` hiçbir zaman içerik kuralıyla ya da `MODE` ile reddedilmez.** Durmak her
durumda güvenlidir. Konum inancı bile taşımaz, çünkü tutarlılık denetimi bir durdurma
komutunu engellememeli. Yalnızca `AUTH`, `REPLAY` ve `FRESHNESS` uygulanır. Araca `HALT(0)`
gider (Nav2 hedefi iptal). `RECOVERY`'de kurtarmayı bitirir (`HOLD`), ret serisini
sıfırlamaz (K-048). `bekle()` ise görev komutudur: `NORMAL` dışında `MODE` ile ret, kabulde
`HALT(süre)`.

**`AUTH` ve `REPLAY` retlerinde karttan hiçbir cevap çıkmaz.** Yalnızca `STATUS`
sayaçları artar. İmzası tutmayan bir göndericiye neyin yanlış olduğunu söylemek
saldırgana bilgi verir. Üstelik imzasız girdinin karttan cevap tetiklemesi, kartı yukarı
yönü boğmak için kullanılabilir hâle getirir (`docs/protocol.md` §4.7).

---

## 3. Kural ayrıntıları

### 3.1 Coğrafi sınır

- **Model:** bir **izinli çokgen** (dış sınır) ve sıfır ya da daha fazla **yasak çokgen**
  (iç delikler). Nokta ancak izinli çokgenin içinde ve hiçbir yasak çokgenin içinde
  değilse geçerlidir. Tüm koordinatlar harita çerçevesinde (`map`), metre cinsinden.
- **Test:** ışın atma (ray casting) ile nokta-çokgen testi.
- **Boyut üst sınırları**: izinli çokgen ≤ 16 köşe · ≤ 4 yasak çokgen, her biri
  ≤ 8 köşe. En kötü durumda nokta başına 48 kenar testi yapılır. Sınırlı olması,
  karar süresinin garanti edilebilmesi için gerekir.
- **İki ayrı yüz:** *hedef* dışarıdaysa komut reddedilir. *Araç* dışarıdaysa ret işe
  yaramaz, çünkü sürüklenme ya da atalet yüzünden zaten dışarıdadır. Bu durumda
  kurtarma devreye girer.
- **Yalnızca hedef ve canlı konum denetlenir, rota denetlenmez.** İzinli bir hedefe giden
  yol yasak bölgeden geçebilir. Bunu önlemek Nav2'nin yasak bölge filtresinin işi. Yol
  yine de yasak bölgeye girerse canlı konum denetimi yakalar.
- **Koordinatlar Faz 3'te doldurulacak.** Harita henüz yok.

### 3.2 Fiziksel limitler: hız komutunda kırpma

Önce ivme, sonra hız kırpılır. İvme yalnız **hızlanmada** kırpılır (K-046):

```
hızlanma (v · v_önceki ≥ 0 ve |v| > |v_önceki|):  v' = clamp(v, v_önceki − Δv_max, v_önceki + Δv_max)
aksi (yavaşlama, durma, işaret değişimi):          v' = v
v'' = clamp(v', −0,60,  +0,60)
(açısal için aynısı: Δω_max ve ±0,6)
```

- **Yavaşlama kırpılmaz:** durmayı geciktirmek tehlikelidir (§2: `dur()` hiçbir zaman
  reddedilmez). Ölçüldü: Nav2'nin yumuşatıcısında yavaşlama −1,0 m/s² ile sınırlıyken RPP'nin
  "collision ahead" durdurmasında araç 12 cm daha ilerleyip keepout'a girdi ve kurtulamadı.
- **İşaret değişimi yavaşlama sayılır,** Nav2'nin `velocity_smoother`'ıyla aynı tanım. Böylece
  Nav2'nin normal çıktısı hiç kırpılmaz (sıfırın ötesini hızlanma sayan tanımla 5 150 komutta
  2 kırpma olurdu). **Bilinen sınır:** yön değişiminde ani sıçrama (en çok ±0,6 → ∓0,6)
  sınırlanmaz.

- `v_önceki` = **son gönderilen (kırpılmış) komut**, son *alınan* değil. Aracın gerçekte
  ne duyduğuyla kıyaslanmalı. `BEKLE`'den çıkışta 0 kabul edilir.
- **İvme, bölme yapmadan, komut başına hız farkı olarak denetlenir**:
  `Δv_max = 0,6 × 0,05 = 0,03 m/s` ·
  `Δω_max = 1,2 × 0,05 = 0,06 rad/s`, burada `T = 50 ms` Nav2'nin 20 Hz'lik periyodu.
  Karşılaştırma için Nav2'nin kendi açısal basamağı 1,0 × 0,05 = 0,05 rad/s.
- **Neden ölçülen Δt değil sabit T:** gerçek varış aralıkları titrer. 50 ms yerine
  30 ms sonra gelen bir komut, ivmeyi olduğundan yüksek gösterir ve haksız kırpmaya
  yol açar. Sabit T bölme gerektirmez, titremeden etkilenmez ve süresi sabittir.
  **Varsayım:** Nav2 20 Hz'de çalışıyor. **Doğrulandı (2026-10-14):** `velocity_smoother`
  kendi zamanlayıcısıyla sabit 20 Hz yayınlar (aralık en çok 52 ms); onsuz kurtarma
  hareketleri 10 Hz geliyordu (`behavior_server` `cycle_frequency`). Frekans değişirse bu
  değerler güncellenir.
- **Kartta uygulandı (2026-10-14):** `firmware/app/rules/limits/` (mm/s, mrad/s, tamsayı;
  adım 30 mm/s · 60 mrad/s). Nav2'nin normal sürüşünde 903 komutta 0 kırpma (K-046'nın amacı:
  Nav2'nin çıktısı kırpılmaz). Kırpmalar `STATUS.clipped`'te.

### 3.3 Tazelik

- Komut yaşı = kartın şimdiki zamanı − komutun zaman damgası. Kabul aralığı
  **−50 ms ≤ yaş ≤ 200 ms**. Kalp atışı dahil ajan kanalındaki her imzalı çerçeveye uygulanır.
- **Alt sınır neden var:** zaman damgası kartın saatinden 50 ms'den fazla ileride olamaz.
  50 ms eşitleme hatasına tanınan paydır. Daha büyük bir fark eşitlemenin bozulduğunu
  gösterir. Böyle bir komut kabul edilseydi tazelik denetimi fiilen devre dışı kalırdı.
- 20 Hz'lik hız akışında bu 4 periyot eder. Birkaç gecikmiş pakete tolerans tanır ama
  bayat komutu geçirmez.
- Görev komutlarında zaman damgası LLM'in düşünmeye başladığı an değil, komutun
  **gönderildiği an**dır. LLM'in saniyelerce düşünmesi tazeliği etkilemez.
- **Zaman eşitleme** her kalp atışında yapılır, hata birkaç ms (`docs/protocol.md` §6).
- **Uygulandı (2026-10-14):** kart `firmware/app/rules/freshness/` (yaş işaretli 32 bit fark,
  saat taşmasında doğru), ajan kanalının her imzalı çerçevesinde, REPLAY'den sonra. Görev
  komutu ve `SIFIRLA` VERDICT alır (value yaş, lo −50, hi 200), hız komutu ve kalp atışı
  sessizce düşer, `STATUS.err_fresh` sayılır, ret serisine girmez. Ölçüldü: RTT 7–11 ms;
  500 ms geri alınmış damga kartta 505–507 ms, 200 ms ileri alınmış −192 ms; Nav2'nin
  sürüşünde 897 komutta 0 bayat.

### 3.4 Tutarlılık

Görev komutu, ajanın varsaydığı araç konumunu ve **bu konumu okuduğu anın zaman
damgasını** taşır. Kart bunu en son telemetriyle kıyaslar:

```
tol(Δt) = d₀ + v_max × Δt
d₀    = 0,25 m   (konum gürültüsü payı)
v_max = 0,60 m/s (bekçinin kendi hız limiti)
Δt    = şimdi − ajanın konumu okuduğu an,  Δt ≤ 10 s
```

- **Tolerans neden sabit değil:** LLM, özellikle CPU'da çalışırsa, konumu okuduktan
  sonra saniyelerce düşünebilir. O sırada araç hareket eder. 0,5 m gibi sabit ve dar
  bir tolerans dürüst komutları da reddeder (yanlış alarm).
- **Formül neden güvenilir:** bekçi hızı zaten 0,60 m/s'de kestiği için araç Δt sürede
  en fazla `v_max × Δt` yol alabilir. Tolerans fiziksel bir üst sınırdan türetiliyor,
  tahmine dayanmıyor.
- **Konum bilgisi 10 s'den eskiyse** komut `CONSISTENCY` ile reddedilir ve gerekçede
  "konumu yeniden oku" denir. 10 s'de tolerans 3,25 m'ye çıkar. Daha eskisi anlamlı
  bir denetim bırakmaz.
- Bu kural ince hataları değil, **kaba hataları** yakalamak için var: yanlış koordinat
  çerçevesi, yer değiştirmiş x/y, uydurulmuş konum. Bunlar genelde metrelerce sapar.
- **Telemetri 500 ms'den eskiyse** tutarlılık denetlenemez. Komut `CONSISTENCY /
  NO_TELEMETRY` ile reddedilir. Denetlenemeyen komut geçirilmez. Eşik kalp atışıyla
  aynı, yeni bir değer eklenmedi.
- Yalnızca konum denetlenir, yön (heading) denetlenmez. Kapsam dışı.

**Sınırlamalar** (tezin sınırlamalar bölümüne girecek):

- **LLM ne kadar yavaşsa kural o kadar gevşer.** Örneğin 1,4 m'lik bir x/y yer değiştirme
  hatası Δt = 1 s'de yakalanır (tolerans 0,55 m) ama Δt = 5 s'de kaçar (tolerans 1,75 m).
  Faz 4'teki model seçimi (CPU mu GPU mu) kuralın gücünü doğrudan etkiler. Her kararın
  Δt'si kayda geçtiği için Faz 6'da **"LLM gecikmesine göre yakalama oranı"** ek bir
  özellik gerekmeden çizilebilir.
- **Araç dururken de tolerans büyür.** Daha sıkı bir alternatif, telemetri geçmişinden
  aracın gerçekte ne kadar yol aldığını hesaplamak. Ama bu, kartta konum geçmişi saklamayı
  ve karar süresini değişken yapmayı gerektirir. Basit formülde kalındı.

### 3.5 Kalp atışı

- Gönderen: **köprü** (`guard_bridge`), LLM değil. LLM saniyelerce düşünebilir, onun
  sessizliği bağlantı kopması sayılmamalı.
- Periyot **100 ms**, zaman aşımı **500 ms**. Art arda 4 kayba tolerans tanır.
- 0,60 m/s'de 500 ms, durma kararından önce en fazla **30 cm** yol demek.
- Ölçüm kartta bir donanım zamanlayıcısıyla yapılır, yazılım döngüsüne bağlı değildir.

### 3.6 Kimlik ve tekrar

- HMAC etiketinin uzunluğu ve anahtar yönetimi `docs/protocol.md`'de. Anahtar depoya
  girmez (K-007).
- Sayaç kesin artan olmalı. Aradaki boşluklar (kayıp paketler) kabul edilir.
- **Sayaç, imza doğrulandıktan hemen sonra güncellenir, komut sonraki bir kuralda
  reddedilse bile.** Aksi hâlde, örneğin `MODE` ile reddedilmiş imzalı bir komut, kart
  `NORMAL`e döndükten sonra yeniden oynatılıp kabul ettirilebilir.

---

## 4. Denetim sırası

Kurallar sabit bir sırayla işler. **İlk ihlal eden kural gerekçeyi belirler.**

| # | Denetim | Neden bu sırada |
|---|---|---|
| 1 | Çerçeve, CRC, tip/kanal/yön/uzunluk | Bozuk çerçeve sessizce atılmaz, **sayılır ve raporlanır** |
| 2 | `AUTH` | İmzası doğrulanmamış bir mesajın içeriği hiç ayrıştırılmaz |
| 3 | `REPLAY` | Sayaç burada güncellenir (§3.6) |
| 4 | `FRESHNESS` | |
| 5 | `MODE` | Kurtarma ya da beklemede görev komutları içerik denetimine girmez |
| 6 | `GEOFENCE` · `LIMIT` · `CONSISTENCY` | İçerik kuralları |

**Güvenlik ilkesi: kartın durumunu yalnızca imzası doğrulanmış mesajlar değiştirebilir.**
Sayaç, ret sayacı ve durum makinesi 2. adımı geçemeyen hiçbir mesajdan etkilenmez.
Böylece imzasız mesaj yağdıran biri kartı kurtarmaya zorlayamaz.

Tek istisna `HELLO_REQ`: köprünün oturum bilgisini istediği imzasız mesaj. Kartın
durumunu **değiştirmez**, yalnızca `HELLO` cevabını tetikler. Cevap da saniyede 2 ile
sınırlıdır (`docs/protocol.md` §5.3).

---

## 5. Kurtarma

### 5.1 İlke (K-010)

**Kart kör sürmez.** Nav2'nin hız komutları ajan kanalından geçip karta döndüğü için
Nav2 yalnızca **ajan kanalı canlıyken** kullanılabilir:

```
Kart ──hedef──▶ Nav2 ──hız komutu──▶ Kart ──onaylı hız──▶ İKA
     (araç kanalı)     (ajan kanalı)       (araç kanalı)
```

- **Kanal canlı:** kart kayıtlı bir noktayı Nav2'ye hedef olarak gönderir. Nav2 engelden
  kaçarak sürer, kart onun her hız komutunu denetlemeye devam eder.
- **Kanal ölü:** kart araç kanalından doğrudan sıfır hız gönderir ve bekler.

Kart hiçbir zaman planlayıcısız hareket üretmez. Düz çizgide ölü hesap ile sürüş,
engel riski yüzünden kullanılmaz.

### 5.2 Durum makinesi

| Durum | Kod | Görev komutları | Hız komutları | Kart araca ne gönderir |
|---|---|---|---|---|
| Normal | `NORMAL` | tüm kurallarla denetlenir | tüm kurallarla denetlenir | onaylı komutlar |
| Kurtarma | `RECOVERY` | `MODE` ile ret | denetlenir, geçer | Nav2'nin onaylı komutları |
| Bekle | `HOLD` | `MODE` ile ret | yok sayılır | **20 Hz'de sıfır hız** |

| Geçiş | Tetikleyen |
|---|---|
| **açılış → `HOLD`** | Kart her zaman güvenli durumda açılır |
| `NORMAL` → `HOLD` | kalp atışı zaman aşımı · araç yasak bölgede ve kanal ölü |
| `NORMAL` → `RECOVERY` (hedef: **başlangıç**) | üst üste 5 içerik reddi, kanal canlı |
| `NORMAL` → `RECOVERY` (hedef: **en yakın güvenli nokta**) | araç yasak bölgede, kanal canlı |
| `RECOVERY` → `HOLD` | hedefe varıldı (≤ 0,35 m) · kalp atışı zaman aşımı · telemetri 500 ms yok · 180 s geçti (K-047) · `dur()` (K-048) |
| `HOLD` → `NORMAL` | yalnızca imzalı **`SIFIRLA`** komutu, kalp atışı canlıyken |

- **Kurtarma her zaman `HOLD`'da biter. `NORMAL`'e dönüşün tek yolu `SIFIRLA`.**
  Kalp atışının geri gelmesi tek başına yetmez (mandallı arıza). Bağlantı gidip gelirken
  aracın kendiliğinden yeniden hareketlenmesi istenmez.
- **`HOLD`'a her girişte araca bir kez `HALT(0)` gider (K-042):** araç köprüsü Nav2'nin
  hedefini iptal eder; bağlantı kopunca ve kart yeniden başlayınca da. Böylece `SIFIRLA`'dan
  sonra araç, ajan yeni hedef verip kart onaylayana kadar kıpırdamaz (doğrulandı 2026-10-14).
- **`HOLD`'da sıfır hız sürekli gönderilir**, çünkü araç tarafının son komutu tutup
  tutmadığına güvenilmez.
- **Açılışta `HOLD`**, çünkü kart yeniden başladığında sayaç durumu sıfırlanmıştır.
  Oturumun yeniden kurulması (`docs/protocol.md`) `SIFIRLA`'dan önce gelir.

### 5.3 Kurtarma noktaları

- **Başlangıç noktası** ve **güvenli noktalar** (≤ 8) harita çerçevesinde
  kayıtlıdır (`shared/site/ika_saha.yaml`). **Seçim ölçütü:** araç noktada her yönde durup
  dönebilmeli: Nav2'nin izi + payının dönüş yarıçapı (1,56 m) içinde harita engeli ya da
  keepout hücresi yok. Böylece kartın gönderdiği varış yönü (0) önemsiz. Denetim:
  `shared/site/tests/test_safe_points.py` (iz ve pay Nav2 ayarından okunur). İlk seçim bu
  ölçütü karşılamıyordu: Nav2 iki noktaya ulaşamıyordu (2026-10-14, STATUS).
- **En yakın:** mevcut telemetri konumuna düz çizgi (Öklid) uzaklığı en küçük olan. Eşitlikte
  sıra numarası küçük olan seçilir. Düz çizgi uzaklığı yol uzaklığı değildir. Gerçek
  rotayı Nav2 planlar.
- **Varış toleransı: 0,35 m**. Nav2'nin hedefe varış toleransından
  (`xy_goal_tolerance`) **büyük olmalı.** Küçük olursa Nav2 "vardım" deyip durur,
  kart ise varışı hiç görmez ve `RECOVERY`'de takılır. **Doğrulandı (2026-10-14):** uçtan uca
  kurtarmada kart varışı gördü ve HOLD'a geçti (Nav2 0,3 m).
- **Zaman kuralları (K-047):** kurtarmada telemetri 500 ms gelmezse ya da kurtarma 180 s'de
  bitmezse `HOLD`. Kart varışı göremiyorsa ya da Nav2 hedefte vazgeçtiyse takılı kalmaz.

### 5.4 Ret sayacı

- Yalnızca imzası doğrulanmış görev komutlarının **içerik** retlerini sayar:
  `GEOFENCE`, `LIMIT`, `CONSISTENCY`. Bunlar ajanın *niyetinin* hatalı olduğunu gösterir.
- **Saymadıkları:** `AUTH`, `REPLAY`, CRC (§4'teki güvenlik ilkesi) · `FRESHNESS`
  (ajanın değil, taşımanın sorunu) · `MODE` (ajanın hatası değil, kartın durumu).
- Kabul edilen bir görev komutuyla ya da `SIFIRLA` ile sıfırlanır. **`dur()` hariç (K-048):**
  araya "dur" koyarak kurtarmadan kaçılamaz.
- **Faz 4'e not:** ajanın görev başına deneme üst sınırı **≤ 4** olmalı. Seçilen değer: **3**.
  5 ya da daha fazla olursa, gerekçeyi kullanıp kendini düzelten dürüst bir ajan kurtarmayı
  tetikler ve S3 ölçümü bozulur.

---

## 6. Deney yapılandırmalarıyla ilişkisi (K-005)

| | Bekçi | Gerekçe |
|---|---|---|
| A | devre dışı | — |
| B | devre dışı (yalnızca Nav2 yasak bölge filtresi ve çarpışma izleyici) | — |
| C | bu belgedeki tüm kurallar | **yok**: ajan yalnızca "reddedildi" görür |
| D | bu belgedeki tüm kurallar | **tam** |

C ile D arasındaki tek fark ajanın gördüğü metin. **Kart iki yapılandırmada birebir
aynıdır** ve her zaman tam gerekçeyi gönderir. C'de gerekçeyi ajandan **köprü** gizler
(`docs/protocol.md` §7.3). Böylece deneydeki tek değişken ajanın gördüğü metindir, firmware
farkı değildir. Hangi kuralın neyi yakaladığı her iki yapılandırmada da tam kaydedilir.
A'da kartın yoldan tamamen mi çıkacağı, yoksa geçirgen modda mı çalışacağı Faz 5'te
kararlaştırılacak.

**S3 için doğal bir ölçüt:** gerekçe almayan ajan (C) körlemesine yeniden dener ve 5 ret
sınırına daha sık ulaşır. **Kurtarmaya düşme oranı** C ile D arasında doğrudan
karşılaştırılabilir.

---

## 7. Açık kalanlar

| Konu | Ne zaman | Not |
|---|---|---|
| Geofence çokgenlerinin koordinatları | Faz 3 | Harita çıkınca |
| ~~Başlangıç ve güvenli noktalar~~ | ✅ 2026-10-14 | §5.3; `ika_saha.yaml` (K-044) |
| ~~Varış toleransı > Nav2 `xy_goal_tolerance`~~ | ✅ 2026-10-14 | §5.3 |
| ~~Nav2 frekansının 20 Hz olduğu~~ | ✅ 2026-10-14 | §3.2; `velocity_smoother` güvencesinde (K-046) |
| Kablo çekme testinde kartın beslenmesi | Faz 2 | STATUS'ta "Bilinen engeller" |

## 8. Kapsam dışı

- **Hızı düşürüp devam et:** Nav2'nin Speed Filter ve Collision Monitor özellikleriyle
  örtüşüyor ve hiçbir araştırma sorusuna katkı vermiyor (K-011).
- **Rota boyunca coğrafi sınır denetimi:** yalnızca hedef ve canlı konum (§3.1).
- **Yön (heading) tutarlılığı:** yalnızca konum (§3.4).
