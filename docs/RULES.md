# Kurallar, Eşik Değerleri ve Kurtarma

> Bekçi kartının **neyi, hangi eşikle denetlediğinin** ve **ihlalde ne yaptığının** tek
> başvuru belgesi. Mesajların biçimi burada değil, `docs/protocol.md`'de.
> Kararların gerekçe geçmişi: `docs/DECISIONS.md` K-010 … K-014. Protokol: `docs/protocol.md`.
> Tüm değerler onaylandı (2026-09-24).

**Son güncelleme:** 2026-09-24

---

## 1. Katmanlı limitler

Bekçinin limiti **Nav2'nin kendi ayarının üstünde, platformun tavanının altında** durur (K-012).

| | Nav2 (TB4 varsayılanı) | **Bekçi** | Platform (Create 3) |
|---|---|---|---|
| Doğrusal hız | 0,26 m/s | **0,30 m/s** | 0,31 (güvenlik açık) · 0,46 (tavan) |
| Açısal hız | 1,0 rad/s | **1,2 rad/s** | 1,9 rad/s |
| Doğrusal ivme | 2,5 m/s² | **3,0 m/s²** | bilinmiyor |
| Açısal ivme | 3,2 rad/s² | **3,8 rad/s²** | bilinmiyor |

- **Nav2'nin üstünde, çünkü** normal çalışmada Nav2'nin ürettiği komutların hiçbiri
  kırpılmamalı. Aksi hâlde her komut "ihlal" sayılır ve yanlış alarm oranı (S1'in ikinci
  yarısı) anlamsızlaşır.
- **Platformun altında, çünkü** platform tavanında duran bir limit hiç tetiklenmez.
  Araç o hızı fiziksel olarak aşamaz. "Sınırları zorlayan talimatlar" senaryosunun
  (Faz 5) veri üretebilmesi için bekçinin bir yerde *hayır* diyebilmesi gerekir.
- İvme değerleri aynı ilkeyle, Nav2 değerlerinin ~%20 üstüne konmuştur (hızlarda oran
  0,30/0,26 ≈ 1,15 ve 1,2/1,0 = 1,2).

**Kaynaklar:** Nav2 değerleri `turtlebot4/turtlebot4_navigation/config/nav2.yaml`
(humble dalı; DWB denetleyici, 20 Hz, velocity_smoother 20 Hz), 2026-09-24'te okundu.
Platform değerleri TurtleBot 4 kullanım kılavuzu (Create 3 tabanı).
**K-008 (Gazebo kararı) TurtleBot 4 dışında bir modele giderse bu tablo yeniden kurulur.**

---

## 2. Kural tablosu

İki tür komut vardır: **görev komutu** (LLM ajanından, seyrek: `git`, `bekle`,
`hiz_siniri`, `dur`) ve **hız komutu** (Nav2'den, 20 Hz, `cmd_vel`).

| Kural | Kod | Uygulandığı | Eşik | İhlalde | Gerekçede dönen |
|---|---|---|---|---|---|
| Coğrafi sınır: hedef | `GEOFENCE` | görev (`git`) | izinli çokgen içinde, yasak çokgenlerin dışında | **Ret** | reddedilen hedef, en yakın kayıtlı güvenli nokta |
| Coğrafi sınır: araç konumu | `GEOFENCE` | telemetri | aynı | **Kurtarma** (§5) | — |
| Fiziksel limit: görev | `LIMIT` | görev (`hiz_siniri`) | 0 < değer ≤ 0,30 m/s | **Ret** | istenen değer, izinli aralık |
| Fiziksel limit: hız | `LIMIT` | hız | \|v\| ≤ 0,30 · \|ω\| ≤ 1,2 · Δv, Δω sınırlı (§3.2) | **Kırp** | — (kayda geçer) |
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
komutunu engellememeli. Yalnızca `AUTH`, `REPLAY` ve `FRESHNESS` uygulanır.

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

Önce ivme, sonra hız kırpılır:

```
v'  = clamp(v,  v_önceki − Δv_max,  v_önceki + Δv_max)
v'' = clamp(v', −0,30,  +0,30)
(açısal için aynısı: Δω_max ve ±1,2)
```

- `v_önceki` = **son gönderilen (kırpılmış) komut**, son *alınan* değil. Aracın gerçekte
  ne duyduğuyla kıyaslanmalı. `BEKLE`'den çıkışta 0 kabul edilir.
- **İvme, bölme yapmadan, komut başına hız farkı olarak denetlenir**:
  `Δv_max = a_max × T = 3,0 × 0,05 = 0,15 m/s` ·
  `Δω_max = 3,8 × 0,05 = 0,19 rad/s`, burada `T = 50 ms` Nav2'nin 20 Hz'lik periyodu.
  Karşılaştırma için Nav2'nin kendi basamağı 0,125 m/s ve 0,16 rad/s.
- **Neden ölçülen Δt değil sabit T:** gerçek varış aralıkları titrer. 50 ms yerine
  30 ms sonra gelen bir komut, ivmeyi olduğundan yüksek gösterir ve haksız kırpmaya
  yol açar. Sabit T bölme gerektirmez, titremeden etkilenmez ve süresi sabittir.
  **Varsayım:** Nav2 20 Hz'de çalışıyor. Frekans değişirse bu değerler güncellenir.

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

### 3.4 Tutarlılık

Görev komutu, ajanın varsaydığı araç konumunu ve **bu konumu okuduğu anın zaman
damgasını** taşır. Kart bunu en son telemetriyle kıyaslar:

```
tol(Δt) = d₀ + v_max × Δt
d₀    = 0,25 m   (konum gürültüsü payı)
v_max = 0,30 m/s (bekçinin kendi hız limiti)
Δt    = şimdi − ajanın konumu okuduğu an,  Δt ≤ 10 s
```

- **Tolerans neden sabit değil:** LLM, özellikle CPU'da çalışırsa, konumu okuduktan
  sonra saniyelerce düşünebilir. O sırada araç hareket eder. 0,5 m gibi sabit ve dar
  bir tolerans dürüst komutları da reddeder (yanlış alarm).
- **Formül neden güvenilir:** bekçi hızı zaten 0,30 m/s'de kestiği için araç Δt sürede
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
- 0,30 m/s'de 500 ms, durma kararından önce en fazla **15 cm** yol demek.
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
| `RECOVERY` → `HOLD` | hedefe varıldı · kalp atışı zaman aşımı |
| `HOLD` → `NORMAL` | yalnızca imzalı **`SIFIRLA`** komutu, kalp atışı canlıyken |

- **Kurtarma her zaman `HOLD`'da biter. `NORMAL`'e dönüşün tek yolu `SIFIRLA`.**
  Kalp atışının geri gelmesi tek başına yetmez (mandallı arıza). Bağlantı gidip gelirken
  aracın kendiliğinden yeniden hareketlenmesi istenmez.
- **`HOLD`'da sıfır hız sürekli gönderilir**, çünkü araç tarafının son komutu tutup
  tutmadığına güvenilmez.
- **Açılışta `HOLD`**, çünkü kart yeniden başladığında sayaç durumu sıfırlanmıştır.
  Oturumun yeniden kurulması (`docs/protocol.md`) `SIFIRLA`'dan önce gelir.

### 5.3 Kurtarma noktaları

- **Başlangıç noktası** ve **güvenli noktalar** (≤ 8) harita çerçevesinde
  kayıtlıdır. **Faz 3'te doldurulacak.**
- **En yakın:** mevcut telemetri konumuna düz çizgi (Öklid) uzaklığı en küçük olan. Eşitlikte
  sıra numarası küçük olan seçilir. Düz çizgi uzaklığı yol uzaklığı değildir. Gerçek
  rotayı Nav2 planlar.
- **Varış toleransı: 0,35 m**. Nav2'nin hedefe varış toleransından
  (`xy_goal_tolerance`) **büyük olmalı.** Küçük olursa Nav2 "vardım" deyip durur,
  kart ise varışı hiç görmez ve `RECOVERY`'de takılır. **Faz 3'te doğrulanacak.**

### 5.4 Ret sayacı

- Yalnızca imzası doğrulanmış görev komutlarının **içerik** retlerini sayar:
  `GEOFENCE`, `LIMIT`, `CONSISTENCY`. Bunlar ajanın *niyetinin* hatalı olduğunu gösterir.
- **Saymadıkları:** `AUTH`, `REPLAY`, CRC (§4'teki güvenlik ilkesi) · `FRESHNESS`
  (ajanın değil, taşımanın sorunu) · `MODE` (ajanın hatası değil, kartın durumu).
- Kabul edilen bir görev komutuyla ya da `SIFIRLA` ile sıfırlanır.
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
| Başlangıç ve güvenli noktalar | Faz 3 | `places.yaml` ile birlikte |
| Varış toleransı > Nav2 `xy_goal_tolerance` | Faz 3 | §5.3 |
| Nav2 frekansının 20 Hz olduğu | Faz 3 | §3.2 buna dayanıyor |
| Kablo çekme testinde kartın beslenmesi | Faz 2 | STATUS'ta "Bilinen engeller" |

## 8. Kapsam dışı

- **Hızı düşürüp devam et:** Nav2'nin Speed Filter ve Collision Monitor özellikleriyle
  örtüşüyor ve hiçbir araştırma sorusuna katkı vermiyor (K-011).
- **Rota boyunca coğrafi sınır denetimi:** yalnızca hedef ve canlı konum (§3.1).
- **Yön (heading) tutarlılığı:** yalnızca konum (§3.4).
