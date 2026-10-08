# Kalıcı Kararlar

> Bu dosyaya **yalnızca eklenir**. Eski kararlar silinmez; değişirse yeni bir madde
> olarak yazılır ve eskisinin "Sonradan değişti" satırı güncellenir.
> Amaç: aynı tartışmayı ikinci kez yapmamak ve tezde "neden böyle yaptın" sorusuna
> hazır cevap bulundurmak.

---

## K-001 · Denetim, LLM'den ayrı bir donanıma taşınır
**Tarih:** 2026-09-22 (proje önerisinde) · **Durum:** Yürürlükte

LLM ajanının ürettiği her komut, araca ulaşmadan önce bağımsız bir STM32
NUCLEO-G474RE kartından geçer. Kart yeni görev üretmez, yalnızca süzer.

**Neden:** Denetim modelle aynı bilgisayarda çalışırsa, o bilgisayar kilitlenince
ya da ele geçirilince denetim de onunla düşer. Literatürdeki Simplex mimarisi
(Sha 2001) ve System-Level Simplex (Bak vd. 2009) bu ayrımı savunur.

---

## K-002 · İki CAN düğümü aynı kart üzerinde
**Tarih:** 2026-09-22 (uygulama planında) · **Durum:** Yürürlükte

Gerçek bir araçta bekçi kartı ile motor sürücü kartı ayrıdır ve CAN ile konuşur.
Elde ikinci kart olmadığı için araç tarafı, aynı Nucleo'nun ikinci FDCAN birimiyle
(FDCAN1 → alıcı-verici → tel → alıcı-verici → FDCAN2) taklit edilir.

**Neden:** Veri gerçekten tellerden geçtiği için CAN davranışı ve gecikmesi gerçektir.
Maliyet ve tedarik süresi ikinci bir kart almayı gerektirmez.
**Tezde nasıl anlatılır:** Bu bir kısaltma değil, tek kartlı bir HIL düzeneğidir;
ölçülen CAN gecikmeleri gerçek hat üzerindedir.

---

## K-003 · Mesaj formatı tek bir yerde tanımlanır
**Tarih:** 2026-09-22 (uygulama planında) · **Durum:** Yürürlükte

Mesajlar yalnızca `shared/protocol/messages.yaml` içinde tanımlanır. Karttaki C
başlık dosyası ve bilgisayardaki Python modülü bu dosyadan **otomatik üretilir**;
hiçbiri elle yazılmaz.

**Neden:** İki tarafta ayrı ayrı elle yazılan format bir gün birbirinden kayar ve
en zor bulunan hatalar buradan çıkar.

---

## K-004 · Hatalar yapay olarak enjekte edilmez
**Tarih:** 2026-09-22 (proje önerisinde) · **Durum:** Yürürlükte

Deneylerde hata enjeksiyonu kullanılmaz; güvensiz komutlar doğrudan LLM'in kendi
doğal hatalarından gelir. Senaryo seti bu hataları tetikleyecek şekilde kurulur
(belirsiz talimatlar, sınırları zorlayan talimatlar, gizlenmiş kötü niyetli talimatlar).

**Neden:** Projenin özgün katkılarından biri. Yapay hata, gerçek LLM hata
dağılımını temsil etmez; ölçüm de o ölçüde inandırıcılığını kaybeder.

---

## K-005 · Dört yapılandırma karşılaştırılır
**Tarih:** 2026-09-22 (proje önerisinde) · **Durum:** Yürürlükte

A: bekçi yok · B: yalnız Nav2 korumaları · C: bekçi var, gerekçe yok ·
D: bekçi var, gerekçe ajana veriliyor (kapalı döngü).
Dördü de **tek bir başlatma parametresiyle** seçilebilmelidir.

**Neden:** S1 A↔C/D, S2 B↔C/D, S3 C↔D karşılaştırmasıyla cevaplanır. Yapılandırma
değiştirmek kod düzenlemeyi gerektirirse deney tekrarlanabilir olmaz.

---

## K-006 · Kapsam kuralı
**Tarih:** 2026-09-22 (uygulama planında) · **Durum:** Yürürlükte

Yeni bir özellik ancak sonuç tablosuna yeni bir satır ekliyorsa eklenir.

**Neden:** 14 hafta dar. Takvim kayarsa önce tutarlılık kuralı, sonra kurtarma
eylemlerinin sayısı azaltılır; araştırma sorularının üçü de korunur.

---

## K-007 · HMAC anahtarı depoya girmez
**Tarih:** 2026-09-22 (uygulama planında) · **Durum:** Yürürlükte

Anahtar hem kartta hem bilgisayarda aynıdır ama `.gitignore`'daki ayrı bir dosyada
durur ve GitHub'a hiçbir zaman yüklenmez. Depo özeldir (private) ama bu yeterli
sayılmaz.

---

## K-008 · Gazebo sürümü kararı Faz 3'e ertelendi
**Tarih:** 2026-09-22 · **Durum:** Açık

Sistemde Gazebo Harmonic kurulu; plan Fortress + TurtleBot 4 simülatörü istiyor.
Faz 1 ve Faz 2 simülasyona ihtiyaç duymadığı için karar Faz 3 başına bırakıldı.

**Seçenekler:**
- *Fortress + TurtleBot 4:* hazır RGB-D kamera, lidar ve sürüş sistemi. Faz 3'ü
  hızlandırır, ~2 GB disk, Harmonic'le yan yana durur.
- *Harmonic'te kalıp kendi modelimiz:* disk tasarrufu, ama İKA modelini, kamerayı
  ve lidarı elle tanımlamak Faz 3'e 1–2 hafta ekler.

---

## K-009 · Mantık analizörü ilk siparişe dahil edilmiyor
**Tarih:** 2026-09-22 · **Durum:** Yürürlükte

Karar süresi ölçümü Faz 2.6'da **DWT çevrim sayacıyla** yapılır. Mantık analizörü
ilk siparişe girmez; aşağıdaki tetikleyicilerden biri olursa alınır.

**Neden:** Planın Faz 2.6 adımı zaten iki ölçüm yöntemi öngörüyor (GPIO pini +
analizör, ve DWT çevrim sayacı). DWT, 170 MHz sistem saatinde **5,9 ns** çözünürlük
verir — 24 MHz'lik analizörün 41,7 ns'sinden yaklaşık 7 kat hassas. S1'in ihtiyaç
duyduğu "kart üzerinde karar süresi" sayısı DWT ile tek başına elde edilebiliyor.
Ayrıca ucuz 24 MHz model Robotistan ve Direnç'te tükenmiş durumda.

**Ne kaybediliyor:** (1) ölçümün bağımsız bir cihazla doğrulanması — DWT yazılımın
kendini ölçmesidir; (2) CAN hattı çalışmazsa telde ne olduğunu görebilme;
(3) UART → karar → CAN zincirinin tek zaman çizgisinde izlenmesi.

**Ne zaman alınır (ikisinden biri olursa):**
- Faz 2.4'te CAN hattı çalışmaz ve üç standart şüpheli (sonlandırma direnci,
  TX/RX ters bağlantı, bit hızı uyuşmazlığı) elendiği hâlde sebep bulunamazsa.
- Faz 5'e (hafta 11) girmeden önce, ölçümü bağımsız doğrulamak için.

**Alınırsa şart:** CY7C68013A / FX2LP çipli olmalı; sisteme kurulu
`sigrok-firmware-fx2lafw` ve PulseView yalnızca bunları tanır.

**Not:** GPIO ölçüm pini (`firmware/app/timing/`) yine de kodlanır. Analizör
sonradan alınırsa ek iş çıkmasın diye pin baştan hazır bırakılır.

---

## K-010 · Kurtarma: kart kör sürmez
**Tarih:** 2026-09-24 · **Durum:** Yürürlükte · **Ayrıntı:** `docs/RULES.md` §5

Kurtarmada kart tek bir soruya bakar: **ajan kanalı canlı mı?**
- **Canlı:** kayıtlı bir noktayı (başlangıç ya da en yakın güvenli nokta) Nav2'ye hedef
  olarak gönderir. Nav2 sürer, kart onun her hız komutunu denetlemeye devam eder.
- **Ölü:** araç kanalından doğrudan sıfır hız gönderir ve bekler.

Kart üç durumlu bir makineyle çalışır (`NORMAL` / `RECOVERY` / `HOLD`). Her zaman
`HOLD`'da açılır. Kurtarma her zaman `HOLD`'da biter. `NORMAL`'e dönüş yalnızca imzalı
`SIFIRLA` komutuyla olur.

**Neden:** Nav2'nin hız komutları ajan kanalından geçip karta döner. Kanal ölüyse Nav2
çalışıyor olsa bile araca ulaşamaz. Kartta planlayıcı, harita ya da engel algılama yok.
Kendi başına bir noktaya gitmeye kalkarsa düz çizgide kör sürer ve engele çarpabilir.
Bu kararla araç ya gerçek bir planlayıcı tarafından sürülür ve kart onu denetler, ya da
durur. Simplex ilkesine de uyar: karmaşık bileşen sürer, basit bileşen karar verir ve
denetler. "Kart yeni görev üretmez" ilkesi korunur, çünkü kart yalnızca önceden kayıtlı
noktalardan birini seçer.

**Öneriye göre değişenler:**
- "Kalıcı kopmada eve dön" kaldırıldı. Kanal ölüyse Nav2'ye ulaşılamaz, eve dönüş kör
  sürüş olurdu.
- Tutarlılık ihlali, önerideki haline döndü: **ret + uyarı**, kurtarma değil. Yanlış
  olan aracın konumu değil, ajanın varsayımı.

**Bedeli:** güvenli nokta listesi, varış toleransı ve üç durumlu makine.

---

## K-011 · "Hızı düşürüp devam et" kapsam dışı
**Tarih:** 2026-09-24 · **Durum:** Yürürlükte

Önerideki dört kurtarma eyleminden biri çıkarıldı. Kalanlar: yerinde bekle, en yakın
güvenli noktaya git, başlangıca dön.

**Neden:**
- **Hiçbir araştırma sorusuna katkı vermiyor.** S1 güvensiz komutların yakalanmasını
  ölçer, yavaşlamak bir komut yakalamak değildir. S3 ret gerekçesiyle ilgilidir.
- **S2'de ayırt edici değil.** Nav2'nin aynı işi yapan iki özelliği var: haritadaki
  bölgelere göre hız düşüren Speed Filter ve engele yaklaşınca yavaşlatan Collision
  Monitor. B ve D yapılandırmaları bu açıdan farklılaşmaz.
- **Gerçek maliyeti "iki eşik" değil:** yaklaşma mesafesi, tutarlılık uyarı bandı,
  yavaşlatma oranı, histerezis (sınırda titremeyi önlemek için), çokgen kenarına uzaklık
  hesabı ve Faz 5'te ayrı senaryolar.
- Planın B planı, takvim kayarsa ilk önce kurtarma eylemi sayısını azaltmayı söylüyor.
  Bu eylem zaten ilk kesilecek adaydı. Kapsam kuralı (K-006) gereği baştan çıkarıldı.

**Tezde:** "Önerilen dört eylemden 'hızı düşürüp devam et', Nav2'nin Speed Filter ve
Collision Monitor özellikleriyle örtüştüğü ve bekçinin katkısını ayırt etmediği için
kapsam dışı bırakıldı."

**Karıştırılmaması gereken:** fiziksel limitte **sınıra kırpma** kalıyor. O tek bir
komuta uygulanır, durum tutmaz ve ek eşik istemez.

---

## K-012 · Eşik değerleri: katmanlı hız limitleri ve orta zaman profili
**Tarih:** 2026-09-24 · **Durum:** Yürürlükte · **Ayrıntı:** `docs/RULES.md` §1–§3

- **Hız:** bekçi 0,30 m/s ve 1,2 rad/s. Nav2'nin TB4 varsayılanı (0,26 · 1,0) ile
  platform tavanı (0,46 · 1,9) arasında.
- **Zaman:** tazelik 200 ms, kalp atışı zaman aşımı 500 ms.

**Neden hız bu aralıkta:** Nav2'nin altında olsaydı normal komutlar sürekli kırpılır ve
yanlış alarm oranı anlamsızlaşırdı. Platform tavanında olsaydı hiç tetiklenmez ve
"sınırları zorlayan talimatlar" senaryosu veri üretmezdi.

**Neden orta profil:** 200 ms, 20 Hz'lik akışta 4 periyot eder. Birkaç gecikmiş pakete
tolerans tanır ama bayat komutu geçirmez. 500 ms kalp atışı, 0,30 m/s'de durma
kararından önce en fazla 15 cm yol demek. Daha sıkı değerler PC yükü altında yanlış
alarmı artırır. Daha gevşekleri güvenli moda geçiş süresini kötüleştirir.

**Görev komutunda limit aşımı ret, hız komutunda kırpma.** LLM'in `hiz_siniri(0,4)`
isteği niyet gösterir. Reddedilirse S1'de yakalandı sayılır ve D'de ajan düzeltebilir.
Nav2'nin hız komutu bir kontrol döngüsünün çıktısıdır. Kırpmak yeterli, reddetmek aracı
sarsar.

**Bağımlılık:** Nav2 değerleri TurtleBot 4 varsayılanından alındı. K-008 başka bir
modele giderse yeniden bakılır.

---

## K-013 · Önerilen eşikler onaylandı. C/D farkı köprüye taşındı
**Tarih:** 2026-09-24 · **Durum:** Yürürlükte · **Ayrıntı:** `docs/RULES.md`

**Onaylanan değerler:**

| Değer | Karar | Gerekçe |
|---|---|---|
| İvme | 3,0 m/s² · 3,8 rad/s² | Nav2'nin ~%20 üstü, hızlarla aynı ilke |
| İvme denetimi | komut başına Δv ≤ 0,15 m/s, Δω ≤ 0,19 rad/s | Bölme yok, zaman titremesinden etkilenmez |
| Tutarlılık | **tol = 0,25 m + 0,30 m/s × Δt**, Δt ≤ 10 s | Fiziksel üst sınırdan türetildi (aşağıda) |
| Kalp atışı periyodu | 100 ms | 500 ms zaman aşımına 4 kayıp payı |
| Çokgen sınırları | izinli ≤ 16 köşe, ≤ 4 yasak × 8 köşe | Karar süresi sınırlı kalsın |
| Güvenli nokta | ≤ 8 | Aynı sebep |
| Varış toleransı | 0,35 m | Nav2'ninkinden büyük olmalı |
| Ajan deneme sınırı | 3 (Faz 4) | 5 ret sınırının altında kalmalı |

**Tutarlılık formülünün gerekçesi:** sabit tolerans, ya yavaş düşünen dürüst ajanı
reddeder (dar tutulursa) ya da hızlı ama yanılan ajanı kaçırır (geniş tutulursa). Bekçi
hızı 0,30 m/s'de kestiği için araç Δt sürede en fazla 0,30 × Δt yol alabilir. Tolerans bu
fiziksel üst sınırdan türetildi. Kural, kartın kendi uyguladığı başka bir kurala dayanıyor.
**Bilinen sınırlaması:** LLM yavaşladıkça tolerans genişler, küçük hatalar kaçabilir.
Kural kaba hataları (çerçeve karışıklığı, uydurma konum) yakalamak için tasarlandı.

**C/D değişikliği:** RULES.md'nin ilk hâlinde C yapılandırmasında kart "yalnızca kural
kodunu" gönderecekti. Değiştirildi:
- **C'de ajan hiçbir gerekçe görmez**, yalnızca "reddedildi" görür. Kural kodu bile
  gerekçedir ("GEOFENCE" demek ajana çok şey söyler). C'yi yarım geri bildirimli bir koşula
  dönüştürür ve S3'ü bulanıklaştırırdı.
- **Fark kartta değil köprüde uygulanır.** Kart iki yapılandırmada birebir aynı. Deneyin
  tek değişkeni ajanın gördüğü metin olur, "fark firmware'den mi geldi?" sorusu doğmaz.
  S1 kayıtları C'de de tam gerekçeli.

---

## K-014 · Protokolün temel tasarım kararları
**Tarih:** 2026-09-24 · **Durum:** Yürürlükte · **Ayrıntı:** `docs/protocol.md`

| Karar | Gerekçe |
|---|---|
| **Başlangıç baytı yerine COBS** (0x00 ayraç) | Başlangıç baytı yükte de geçebilir, bozuk uzunluk alanı sonraki çerçeveleri yutar. Bu da planın istediği "bozuk çerçeve sayımını" yanlış çıkarırdı. COBS senkronu tek baytta geri kazanır, maliyeti 1 bayt. |
| **Hattaki her sayı tamsayı**, kayan nokta yok | `NaN > 0,30` yanlış döner. NaN taşıyan hız komutu limit denetiminden sessizce geçerdi. |
| **Hem CRC hem HMAC**, ayrı sayaçlar | Gürültü (hat kalitesi) ile saldırıyı (S1'de yakalanan) ayırt etmek için. |
| **8 baytlık (64 bit) etiket** | 115200 baud'da kaba kuvvet ~1,3 milyar yıl. Tam etiket hız komutunu iki katına çıkarırdı. |
| **Oturum kimliği imzaya girer**, hatta gönderilmez | Kart yeniden başlayınca sayaç sıfırlanır. Eski oturumun çerçeveleri AUTH ile düşer. Flash'a sayaç yazmaya gerek kalmaz. |
| **Şema özeti HELLO'da** | Kart ile köprü farklı `messages.yaml`'dan derlenmişse ilk bağlantıda açıkça ortaya çıkar. K-003'ün çalışma zamanı denetimi. |
| **Porta göre güven** | `TELEMETRY` yalnızca araç kanalından kabul edilir. Ajan tarafı telemetri uyduramaz, kriptografiye gerek kalmaz. |
| **Yön, kimliğin üst bitinde** | Karta geri yansıtılan kendi çerçevesi tek bit testiyle düşer. |
| **Zaman eşitleme her kalp atışında** | Kart saati saatte 0,2 s (HSE) ile 36 s (HSI) arası kayar. Tek seferlik eşitleme yetmez. Hata ≤ RTT/2, yani birkaç ms. |
| **İmzasız girdiye sessiz ret** | Kart AUTH/REPLAY/CRC retlerinde cevap vermez, yalnızca sayaç tutar. Saldırgana bilgi sızmaz, kart yukarı yönü boğmak için kullanılamaz. |
| **Uzunluk alanı yok**, tipe göre tam eşitlik | Bozulabilecek bir alan daha az. |
| **CAN kimlikleri öncelik sırasında**, HALT en küçük | CAN tahkiminde küçük kimlik kazanır. Durdurma komutu hiçbir mesajın arkasında beklemez. |
| **`dur()` içerik kuralı ve MODE'dan muaf** | Durmak her durumda güvenlidir. Hiçbir denetim bir durdurma komutunu engellememeli. |

**Planla karşılaştırma:** plan "başlangıç baytı, mesaj tipi, sayaç, zaman damgası, yük,
HMAC etiketi, CRC" diyordu. Başlangıç baytı dışındaki her alan aynen var. Başlangıç
baytının amacı (çerçeve sınırı) COBS ayracıyla, daha güvenilir biçimde karşılandı.

**Tehdit modeli notu (tezde açıkça yazılmalı):** HMAC, LLM'in hatalı ya da kötü niyetli
komutlarını **yakalamaz**. O komutlar meşru boru hattından geçer ve imzalanır. Onları içerik
kuralları yakalar. HMAC kanala dışarıdan enjeksiyonu ve tekrarı yakalar. PC anahtarla birlikte
tamamen ele geçirilse bile içerik kuralları, limitler ve kalp atışı çalışmaya devam eder.
HMAC bir katmandır, güvenliğin temeli bağımsız denetleyicidir.

---

## K-015 · Senaryo başına tekrar sayısı
**Tarih:** 2026-09-24 · **Durum:** Yürürlükte

Plan bu kararı Faz 1'de hocayla vermeyi öngörüyordu. Hoca müsait olmadığı için
gerekçesiyle burada verildi.

| Senaryo türü | Tekrar |
|---|---|
| LLM'e bağlı (normal, belirsiz, sınırları zorlayan, gizlenmiş kötü niyetli) | **20** |
| Altyapı arızası (ajanın donması, bağlantı kopması) | **10** |

Her senaryo dört yapılandırmanın (A–D) hepsinde bu sayıda koşulur.

**Neden 20:** tek bir hücrede (1 senaryo × 1 yapılandırma) %50 civarı bir oranın %95
güven aralığı ±%22. Analiz kategori bazında yapılır: kategori başına 3 senaryo × 20 = 60
koşu, aralık ±%13. Bu, yapılandırmalar arası farkları göstermeye yeter. Sonuçlar Wilson
güven aralığıyla raporlanır, çıplak yüzdeyle değil.

**Neden arızada 10:** ölçülen güvenli moda geçiş süresi LLM'e bağlı değil ve değişkenliği
düşük. Kablo çekme elle yapılabilir.

**Zaman bütçesi** (kategori başına 3 senaryo varsayımıyla): 12 × 4 × 20 + 2 × 4 × 10 =
**1040 koşu**. Koşu başına 2–5 dk ile 35–87 saat. Faz 5'in 2 haftasına, geceleri otomatik
koşularak sığar.

**Güvenlik payı:** Faz 5 başında her senaryo D'de 3 kez pilot olarak koşulur ve gerçek
koşu süresi ölçülür. Bütçe aşılıyorsa tekrar 15'e iner, **daha aşağı inmez**. Senaryo ve
yapılandırma sayısı kesilmez, çünkü S1–S3 karşılaştırmaları hepsine ihtiyaç duyar.

**Bağlı kararlar (Faz 4):**
- **Sıcaklık > 0 olmalı.** Sıcaklık 0'da LLM hemen hemen belirlenimci olur ve tekrarlar
  aynı şeyi ölçer. K-004 hataların doğal dağılımdan gelmesini istiyor. Kesin değer modelle
  birlikte seçilip kaydedilecek.
- **Seed = tekrar numarası** (destekleniyorsa). Böylece bir tekrarın ilk komutu dört
  yapılandırmada birebir aynı olur ve karşılaştırma eşleştirilmiş olur: aynı güvensiz komut
  A, B, C ve D'ye ayrı ayrı sunulur. Ollama `seed` destekliyor. Faz 4'te belirlenimcilik
  doğrulanacak (GPU'da tam garanti değil, bazı API'lerde seed yok).

---

## K-016 · Saat kaynağı: HSE kristali, 170 MHz
**Tarih:** 2026-09-24 · **Durum:** Yürürlükte

Kart, NUCLEO-G474RE üzerindeki 24 MHz kristalden (HSE) PLL ile 170 MHz'de çalışır
(PLLM /6, ×85, /R /2). CubeMX'in kart için hazır ayarı PLL'i dahili RC osilatörden (HSI)
beslediği için elle değiştirildi.

**Neden:**
- **Ölçüm doğruluğu.** DWT ile ölçülen karar süreleri, saatin tam 170 MHz olduğu
  varsayımıyla mikrosaniyeye çevrilir. HSI'nın ±%1 toleransı, S1'deki her gecikmeye ±%1
  sistematik hata ekler. Kristalde bu ihmal edilebilir.
- **Temsil gücü.** Gerçek araçta ayrı kartlardaki CAN düğümleri sıkı saat toleransı ister.
  Tek kartlı düzenekte (K-002) iki FDCAN aynı saati paylaştığı için HSI ile de çalışırdı,
  ama HSE ile düzenek gerçeğe daha yakın kalır.
- **Maliyeti yok.** Kristal kartta hazır.

**Not:** zaman eşitlemesi HSE'yi gerektirmez. Her kalp atışında yenilendiği için kayma
birikmez (`docs/protocol.md` §6.1).

---

## K-017 · Ajan kanalı: CubeMX'te LPUART1, alma DMA ile
**Tarih:** 2026-09-26 · **Durum:** Yürürlükte

Ajan kanalı (LPUART1, ST-LINK sanal seri portu, PA2/PA3) CubeMX'te çevre birimi olarak
kurulur, BSP'nin VCP bileşeni kapatılır. Ayar 115200 8N1. Baytlar dairesel DMA ile alınır.
`app_loop()` her turda DMA'nın nereye kadar yazdığına bakar ve yeni baytları işler.

**Neden:**
- **Bekçi hiç beklememeli.** Yoklamalı okumada kart bayt beklerken kalp atışını, araç
  kanalını ve CAN'i izleyemez. 115200 baud'da yaklaşık 87 µs'de bir bayt gelir ve zamanında
  okunmayan bayt kaybolur.
- **Karar süresi ölçümü temiz kalsın (S1).** Bayt başına kesme saniyede yaklaşık 11 500 kez
  işlemciyi böler ve DWT ile ölçülen karar süresine gürültü ekler. DMA'da işlemci bayt başına
  bölünmez.
- **CubeMX'in yeniden üretimi ilk kez basit bir birimde öğrenilsin.** Faz 2.3'te FDCAN için
  CubeMX zaten yeniden çalıştırılacak.

**Bedeli:** BSP'nin `printf` yönlendirmesi VCP ile birlikte gider. Ajan kanalı protokole ait
olduğu için üstüne serbest metin yazılmamalı.

---

## K-018 · Ajan kanalında gönderme de DMA ile
**Tarih:** 2026-09-27 · **Durum:** Yürürlükte

K-017 yalnızca almayı DMA'ya bağlamıştı. Gönderme de DMA ile yapılır (DMA1 kanal 2,
normal mod). LPUART1 kesmesi açıktır: HAL gönderimin bittiğini bu kesmede anlar, hat
hataları da buradan gelir. Bayt başına kesme yine yoktur.

**Neden:**
- **Bekçi gönderirken de beklememeli.** DMA olmadan işlemci her bayt için bekler. En uzun
  çerçeve (44 bayt) yaklaşık 3,8 ms bekleme demek. Gerekçe K-017 ile aynı.
- **CubeMX zaten açıktı.** Sonraya bırakmak ikinci bir yeniden üretim demekti.

**Bedeli:** gönderilecek veri modülün 64 baytlık tamponuna kopyalanır. Önceki gönderim
bitmeden yenisi başlatılamaz, çağıran `agent_link_tx_ready()` ile sorar.

**Doğrulama:** yankı testi, 100 KB, 0 fark, 11 422 B/s (hat sınırının %99,1'i).

---

## K-019 · CAN bit zamanlaması ve gönderme tamponu modları
**Tarih:** 2026-09-28 · **Durum:** Yürürlükte

| Ayar | Değer | Gerekçe |
|---|---|---|
| Saat | PCLK1, 170 MHz (K-016) | Bir bit = 340 saat periyodu |
| Prescaler | 2 → 1 tq ≈ 11,76 ns, bit = 170 tq | Seçilebilecek en küçük değer (1'de Seg1 = 297 > 256). CiA küçük prescaler önerir |
| Bölümler | 1 + 148 + 21, SJW 21 | Örnekleme %87,6. CiA'nın 500 kbit/s için önerdiği %87,5'e en yakın. SJW = Seg2 en geniş düzeltme payını verir |
| FDCAN1 (bekçi) | Kuyruk modu | En küçük kimlik önce gider. HALT, bekleyen DRIVE/GOAL'un önüne geçer |
| FDCAN2 (araç) | FIFO modu | Tek kimlik (TELEMETRY). Kuyruk modu aynı kimlikte tampon sırasına bakar, eski ölçüm yenisinden sonra gidebilirdi |
| Kesme | Yok, alma kuyruğu app_loop()'ta yoklanır | K-017'deki gerekçe: karar süresi ölçümüne kesme gürültüsü girmesin |

**Doğrulama (Faz 2.3, iç döngü):** aynı üç mesaj DRIVE → GOAL → HALT sırasıyla verildi,
GOAL ve HALT DRIVE hattayken. Kuyruk modunda DRIVE, HALT, GOAL; FIFO modunda
DRIVE, GOAL, HALT çıktı. FIFO birimi kontrol deneyidir: sonucun sebebinin şans ya da
zamanlama değil mod olduğunu gösterir.

**Bilinen sınır:** DRIVE hatta çıkmışsa HALT onu kesemez, en fazla bir çerçeve
(~200 µs) bekler. CAN'de başlamış bir gönderim kesilmez.

**Tuzak:** HAL_FDCAN_GetTxFifoFreeLevel() kuyruk modunda hep 0 döner. İlk denemede
bekçi bu yüzden hiçbir mesaj gönderemedi, iç döngü testi bunu kablolamadan önce yakaladı.

---

## K-020 · Araç kanalı: USART1, iki seri kanal tek modülde
**Tarih:** 2026-09-30 · **Durum:** Yürürlükte

Araç kanalı (CP2102 modülü) USART1 üzerindedir: PC4 (TX), PC5 (RX), kartta D1/D0. Ayar
115200 8N1, akış kontrolü yok. Alma DMA1 kanal 3 ile dairesel, gönderme kanal 4 ile
normal modda yapılır. USART1 kesmesi açıktır. Bu, ajan kanalıyla aynı düzendir (K-017,
K-018). İki kanal tek modülde toplanır: `firmware/app/links/serial_link`. Kanal `port`
parametresiyle seçilir. Almayı durduran her hat hatası türüne göre sayılır: çerçeve (FE),
gürültü (NE), taşma (ORE), diğer.

**Neden:**
- **Bir kavram tek klasörde.** İki kanal da aynı işi yapıyor: bayt taşımak. Ayrı modüller
  aynı DMA kodunu iki kez taşırdı ve bir düzeltmenin iki yere yapılması gerekirdi.
- **Baytın geldiği port kaybolmaz.** Çağıran her baytın hangi porttan geldiğini bilir. Porta
  göre güven (`docs/protocol.md`) bunu gerektiriyor.
- **Bekçi beklememeli, ölçüm temiz kalmalı.** Gerekçe K-017 ile aynı.
- **Hatanın türü sebebini ayırır.** FE ve NE tel ya da elektrik sorununa, ORE yazılımın
  baytları zamanında okuyamadığına işaret eder. Bu, "bozuk veri sessizce atılmaz, sayılır
  ve raporlanır" kuralının (`docs/RULES.md` §1) hat katmanındaki karşılığı. Faz 5'teki
  arıza deneylerinde hat hatalarını ayırt etmek için gerekli.
- **Pin seçimi.** USART1 bu çipte PA9/PA10, PB6/PB7 ve PC4/PC5'e çıkabiliyor. Üçü de
  boştaydı. PC4/PC5 seçildi (kartta D1/D0), gerekçesi kaydedilmedi. Başka bir birim
  bu pinleri isterse yer değiştirmek serbest.

**Bedeli:** her kanal yapısı 348 bayt RAM tutuyor, çoğu tamponlar. Tek hatada birden
fazla bit gelebildiği için türlerin toplamı yeniden başlatma sayısından büyük olabilir.

**Doğrulama:** iki kanal aynı anda 100 KB, 0 fark. Araç kanalına yanlış hızda (9600)
5 × `0x00` gönderildi: restarts 5, frame 5, diğerleri 0. Ardından yankı çalıştı.

---

## K-021 · C çerçeveleyici: SHA-256 ve HMAC kendimiz yazıldı, testler PC'de
**Tarih:** 2026-09-30 · **Durum:** Yürürlükte

Çerçeve katmanı iki klasörde:
- `firmware/app/protocol/` → `crc16`, `cobs`, `frame`
- `firmware/app/auth/` → `sha256`, `hmac_sha256`

Bunlar `frame.py`'nin karşılığı. SHA-256 (FIPS 180-4) ve HMAC (RFC 2104) dışarıdan
alınmadı, kendimiz yazdık. Etiket `hmac_tag_equal()` ile sabit zamanlı karşılaştırılır.
Kod kartsız, PC'de gcc ile sınanır: `shared/protocol/tests/test_c_framer.py` kart
kaynaklarını `c_driver.c` ile birlikte derler ve cevapları Python referansıyla
karşılaştırır.

**Neden:**
- **Öğrenme.** Projenin asıl amacı. Algoritma satır satır görülmüş oluyor.
- **Çipte donanım desteği yok.** STM32G474'te HASH birimi yok (CubeMX çip listesi), SHA-256
  zaten yazılımda olacaktı.
- **Bağımlılık ve lisans sorusu yok.** mbedTLS tek fonksiyon için çok büyük. Kopyalanan
  bir kod ise kaynağının ayrıca belgelenmesini gerektirirdi.
- **Doğruluk testle kanıtlanıyor, güvenle değil.** NIST girdileri, RFC 4231'in 7 örneği,
  0–130 bayt her uzunluk ve rastgele bölmelerle `hashlib`/`hmac`'e karşı. Sabitler
  asal sayılardan türetildi.
- **Kart gerektirmeyen test hızlı ve tekrarlanabilir.** Bir değişikliğin doğruluğu bir
  saniyede görülüyor.

**Tasarım kararları:**

| Karar | Gerekçe |
|---|---|
| Çözme tamponu hattın sınırında (64), en uzun mesajda (42) değil | 42 bayttan uzun ama CRC'si doğru bir çerçeve Python'da TYPE (yanlış uzunluk) sayılır. Tampon 42 olsaydı C'de FRAMING olurdu ve iki tarafın sayaçları farklı şey söylerdi |
| `frame_decode()` sayaç tutmaz, türü döndürür | Katman durumsuz kalsın. Sayaçlar, tekrar ve tazelik denetimi alıcının işi (Python'da da öyle) |
| Mesaj bilgileri yalnızca `proto_msg_info()`'dan | Mesaj formatı tek yerde (K-003). Çerçeve kodunda hiçbir mesaj elle tanımlanmadı |
| `hmac_sha256_init()` dış özeti de hazırlar | Hazırlanmış bağlam kopyalanıp her çerçevede kullanılabilir. Karttaki süre ölçümünden sonra gerekirse |

**Bedeli:** Kendi yazdığımız kriptografi kodunun doğruluğundan biz sorumluyuz. Testler bu
yüzden kasıtlı hata konmuş kopyalarla da denendi: 9 hatanın 9'u yakalandı. Zamanlama
davranışı (sabit zamanlı karşılaştırma) PC testiyle kanıtlanamıyor, kartta DWT ile
ölçülecek.

**Doğrulama:** 147 test geçiyor. 17 çerçeve `test_vectors.json` ile bayt bayt aynı,
7 bozuk çerçeve doğru türle reddediliyor, 1 500 rastgele bozulmuş çerçevede ve 100 akışta
C ile Python aynı kararı veriyor.

---

## K-022 · HMAC kartta ölçüldü: etiket her çerçevede baştan hesaplanır
**Tarih:** 2026-10-01 · **Durum:** Yürürlükte

HMAC'in karttaki süresi ve etiket karşılaştırmasının sabit zamanlı olduğu DWT çevrim
sayacıyla ölçüldü (K-009). Sayaç `firmware/app/timing/dwt`'de. Süre sınırın çok altında
kaldığı için hazırlanmış HMAC bağlamı (K-021) **kullanılmıyor**: `frame.c`'nin
`compute_tag`'i anahtarı her çerçevede yeniden hazırlıyor.

**Sonuç** (VERDICT çerçevesi, en uzun yük, net çevrim, 170 MHz):

| | Release (`-Os`) | Debug (`-O0`) |
|---|---|---|
| Tam HMAC (4 blok) | 24 098, **142 µs** | 131 403, 773 µs |
| Hazırlanmış bağlam (2 blok) | 12 730, 75 µs | 65 977, 388 µs |
| `hmac_tag_equal`: eşit / fark 0. bayt / fark 7. bayt | 140 / 140 / 140 | 343 / 343 / 343 |
| `memcmp` (kontrol): eşit / fark 0. bayt / fark 7. bayt | 147 / 48 / 139 | 144 / 45 / 136 |

**Yöntem:** Her ölçüm 1000 kez tekrarlanır, en kısa ve en uzun süre saklanır. Kesmeler her
ölçüm süresince kapalıdır. Ölçmenin kendi maliyeti (boş fonksiyon) çıkarılır. Sonuç RAM'den
salt okuma ile alınır (`docs/STATUS.md`). Kartın etiketi test vektörüyle karşılaştırılır.
`memcmp` kontrol deneyidir: ölçümün bayta bağlı farkı görebildiğini gösterir.

**Neden hazırlanmış bağlam kullanılmıyor:**
- **Süre hat süresinin yanında küçük.** En kısa komut (`VELOCITY_CMD`, 25 bayt) hatta
  2,2 ms sürüyor, tam HMAC 142 µs. Hat tamamen dolu olsa bile (~460 çerçeve/s)
  işlemcinin yaklaşık %6,5'i HMAC'e gidiyor. 20 Hz'lik hız akışında %0,3.
- **Daha az durum, daha az hata yeri.** Hazırlanmış bağlam başlatmada bir kez kurulup
  saklanmak zorunda. Kod `frame.py` ile birebir aynı yapıda kalıyor.

**Bedeli:** Çerçeve başına 67 µs (Release) fazladan süre. Karar süresi ölçümünde (S1) bu
süre sonuca dahil.

**Ne zaman yeniden bakılır:** Karar süresi bütçesi aşılırsa ya da hat hızı artarsa.
Değişiklik `compute_tag`'e sınırlı, `hmac_sha256_init()` dış özeti zaten hazırlıyor.

**Dikkat:** Sabit zamanlılık derleyicinin ürettiği koda bağlı. `-Os`'ta `hmac_tag_equal`'ın
makine kodu `objdump` ile okundu, döngüde erken çıkış yok. Derleyici ya da derleme seçeneği
değişirse ölçüm tekrarlanır.

---

## K-023 · Kanal katmanı: sayaç, oturum ve STATUS `channel/` içinde
**Tarih:** 2026-10-01 · **Durum:** Yürürlükte

Bir seri kanalın protokol durumu `firmware/app/channel/`'dadır: son kabul edilen sayaç
(REPLAY), `STATUS` sayaçları, giden sayaç, oturumun o kanalda kurulup kurulmadığı ve
gönderme kuyruğu. `serial_link` (bayt taşır) ve `frame` (çerçeveyi çözer) durumsuz kalır.
Oturum kimliği açılışta donanım RNG'sinden alınır ve iki kanalda ortaktır. RNG hata
verirse kart çalışmaz.

**Neden:**
- **Sayaç kanalın bilgisidir.** Her kanalın kendi sayaç alanı var (`docs/protocol.md`
  §5.3). Planın klasör yapısı tekrar kontrolünü `auth/`'a koyuyordu. `auth/` imza işi olarak
  kaldı. Sayaç, kanalın diğer durum bilgileriyle aynı yerde: bir kanalın davranışını
  değiştirmek tek klasöre bakmayı gerektiriyor.
- **`HELLO_REQ` sayacı değiştirmez.** İmzasız bir mesaj sayacı ileri itebilseydi, saldırgan
  sayacı yükseltip köprünün meşru çerçevelerini REPLAY ile düşürtebilirdi (RULES §4).
- **Gönderme kuyruğu (4 mesaj).** Hat bir çerçeveyi ~4 ms'de taşıyor. Kuyruk olmasa
  `STATUS` gönderilirken gelen `HEARTBEAT`'in cevabı kaybolurdu. Sayaç ve zaman damgası
  çerçeve hatta çıkarken verilir: `HEARTBEAT_ACK`'in zamanı kuyrukta beklenen süreyi
  içermez (saat eşitleme, §6).
- **RNG'nin saati HSI48.** RNG tam 48 MHz istiyor. PLLQ 340 MHz'den 48'i üretemiyor.

**Bedeli:** Her kanal yapısı 224 bayt RAM. Kuyruk dolarsa mesaj atılır ve `tx_dropped`
artar. Bu sayaç `STATUS`'ta yok, RAM'den okunur.

**Doğrulama:** `tools/link_test.py`, 26 denetim, iki kanal, 5 çalıştırmanın 5'inde geçti
(`docs/STATUS.md`).

---

## K-024 · Coğrafi sınır: sınırın üstü ihlal, tamsayı ışın atma
**Tarih:** 2026-10-01 · **Durum:** Yürürlükte

`firmware/app/rules/geofence/` bir noktayı izinli çokgene ve en fazla 4 yasak çokgene karşı
denetler (RULES §3.1). **Sınırın tam üstündeki nokta her zaman ihlaldir:** izinli çokgenin
kenarı ya da köşesi dışarı, yasak çokgeninki yasak bölge sayılır. Algoritma önce noktanın
bir kenarın üstünde olup olmadığına açıkça bakar, sonra ışın atar (yarı açık kural). Hesap
tamsayıyla, santimetre cinsinden yapılır. Çapraz çarpım 64 bittir. Geçersiz bir sınır
(köşe ya da çokgen sayısı sınırların dışında) hiçbir noktaya izin vermez.

**Neden:**
- **Bekçi şüphede reddeder.** Işın atmanın sınır üstündeki cevabı tanımsızdır, aynı
  kenardaki iki nokta farklı sonuç verebilir. Kenara tam oturan bir hedef, araç gövdesinin
  yarısının dışarıda kalması demek. (Esra'nın kararı, 2026-10-01.)
- **Tamsayı, NaN'siz ve belirlenimci.** Koordinatlar protokolde zaten `int16` cm
  (`docs/protocol.md` §3). PC'deki test ile karttaki kod aynı girdiye birebir aynı cevabı
  verir.
- **64 bit çarpım.** İki çarpımın farkı ±8,6 milyara çıkabilir, 32 bit taşar. Cortex-M4'te
  tek komut. Uç koordinat testi 32 bitlik kopyayı yakalıyor.
- **Hatalı yapılandırma güvenli tarafa düşer.** Gerçek koordinatlar Faz 3'te bir veri
  dosyasından gelecek. Yanlış üretilmiş bir sınır her şeye izin vermektense hiçbir şeye
  izin vermemeli.

**Bedeli:** Çokgenlerin basit olması (kenarların birbirini kesmemesi) burada denetlenmez,
veri üretilirken denetlenmeli (Faz 3). Yasak bölge izinli çokgenin dışına taşıyorsa oradaki
nokta `OUTSIDE_ALLOWED` olarak raporlanır.

**Doğrulama:** `firmware/tests/test_geofence.py`, 45 test, ASan ve UBSan ile. 24 elle
hesaplanmış durum (içbükey "U", ışının köşeden geçtiği noktalar, ±32 767). Dolanma sayısı
kullanan bağımsız Python referansına karşı 51 462 rastgele nokta, 11 236'sı sınırın üstünde.
Kasıtlı hata konmuş 13 kopyanın 13'ü yakalandı.

---

## K-025 · Karar katmanı `guard/`, harita verisi `site/`, araç düğümü `vehicle_node/`
**Tarih:** 2026-10-01 · **Durum:** Yürürlükte

- **`firmware/app/guard/`:** denetim sırası (RULES §4) ve durum makinesi (§5.2). Kuralların
  kendisi `rules/` altında kalır; `guard` hangi kuralın önce baktığını, retin hangi gerekçeyle
  döndüğünü ve durumun nasıl değiştiğini tutar. Donanıma dokunmaz: girdi alır, karar
  (`VERDICT` + gönderilecek `GOAL`) döndürür. Çıktıları göndermek `app.c`'nin işi.
- **`firmware/app/site/`:** coğrafi sınır, başlangıç noktası ve güvenli noktalar bir arada.
  Faz 3'te tek bir harita dosyasından üretilecekler. Şu an `site_data.c`'de deneme verisi.
  Reddedilen hedefin ipucu, **hedefe** en yakın güvenli nokta (eşitlikte sıra numarası küçük).
- **`firmware/app/vehicle_node/`:** FDCAN2, araç tarafı (K-002, protocol.md §8). CAN'den gelen
  onaylı mesajı araç kanalına, araç kanalından gelen `TELEMETRY`'yi CAN'e taşır. CAN kimliği →
  mesaj eşlemesi açılışta üretilmiş tablodan çıkarılır, elle yazılmaz (K-003).
- **`rules/heartbeat/`:** TIM6, 10 kHz, 5 000 sayımda taşar (500 ms). Her geçerli `HEARTBEAT`
  sayacı sıfırlar. Taşma kesmesi "bağlantı öldü" bayrağını kurar, `HOLD`'a geçiş ana döngüde.
- **Karar süresi** çerçevenin son baytı geldiği an başlar (HMAC dahil), `VERDICT` ve CAN
  mesajı kuyruğa girince biter. DWT ile `goto_timing`'e yazılır, PA8 aynı aralıkta 1'dir.
- **`NO_HEARTBEAT` gerekçesi** (protokol, `f7d9822`): kalp atışı yokken gelen `SIFIRLA`'nın
  reddi için. Mevcut gerekçelerden biri ajana yanlış bilgi verirdi.

**Neden:**
- **Bir kavram tek klasörde.** Denetim sırası ile durum makinesi aynı soruya cevap veriyor:
  "bu komuta kart ne yapar". Harita verisinin parçaları aynı kaynaktan gelecek.
- **Karar mantığı PC'de sınanabilmeli.** `guard` donanımdan bağımsız olduğu için gcc ile,
  bellek denetim araçları açık sınanıyor (`firmware/tests/test_guard.py`, 18 test, kasıtlı
  hata konmuş 14 kopyanın 14'ü yakalandı).
- **Kalp atışı yazılım döngüsüne bağlı değil** (RULES §3.5): süreyi donanım ölçüyor.

**Bedeli:**
- **Tepki ana döngüde.** Kesme yalnızca bayrak kuruyor; durum değişikliği ve 20 Hz sıfır hız
  ana döngüden. Ana döngü takılırsa kart `HOLD`'a geçer ama sıfır hız gönderemez. Bunun
  cevabı bağımsız bir bekçi zamanlayıcısı (IWDG) olurdu; kapsam kuralına göre Faz 4–5'te
  değerlendirilecek (STATUS, açık sorular).
- **Faz 4'e kalanlar:** FRESHNESS, LIMIT, CONSISTENCY, RECOVERY durumu (sayaç tutuluyor,
  geçiş yok), `WAIT_CMD`, `SPEED_LIMIT_CMD`, `STOP_CMD`, `VELOCITY_CMD`. Bunlar şu an
  `VERDICT` almıyor.
- **Fiziksel kablo çekme testi yapılmadı.** Kartın beslemesi ajan kanalının USB'sinden
  ayrılmalı (donanım kararı, STATUS "Bilinen engeller").

**Doğrulama:** `tools/decision_test.py` kartta 26 denetim, Debug ve Release'te geçti. Karar
süresi Release'te 169–177 µs.

---

## K-026 · CubeMX komut satırından, değişiklik önce kopyada
**Tarih:** 2026-10-01 · **Durum:** Yürürlükte

CubeMX ayarı, pencere açmadan da yapılabilir: `.ioc`'ye yalnızca istenen satırlar eklenir,
sonra `~/STM32CubeMX/STM32CubeMX -q <betik>` ile `config load <ioc>` ve `project generate`.
Adlar CubeMX'in kendi veritabanından alınır (`db/mcu/IP/*_Modes.xml`, `db/plugins/clock/`).
Değişiklik önce projenin geçici bir kopyasında üretilir, depodakiyle farkı incelenir, ancak
ondan sonra depoya alınır. Üretilen kod her zamanki gibi ayrı bir commit'tir. CubeMX'in
penceresiyle yapılan ayar da geçerliliğini korur.

**Neden:** Esra'nın onayı beklenmeden yürütülen işte (2.6'nın kapanışı) TIM6 ve PA8 gerekti.
CubeMX `.ioc`'yi yüklerken doğruluyor ve kendi düzenine sokuyor (sıralama, eksik kalan
`MX_RNG_Init`'i fonksiyon listesine ekledi). Fark incelendiğinde yalnızca beklenen dosyalar
değişmişti; `.cproject` değişmedi.

**Bedeli:** `.ioc`'nin satır biçimi belgelenmiş bir arayüz değil. Elle eklenen satır yanlışsa
CubeMX onu sessizce düşürebilir. Bu yüzden üretilen kodun farkı her seferinde okunur.

---

## K-027 · Gazebo: Fortress + TurtleBot 4 (K-008'i kapatır)
**Tarih:** 2026-10-05 · **Durum:** Yürürlükte

Faz 3 simülasyonu Gazebo Fortress ve TurtleBot 4'ün Humble simülatörüyle yapılır. Sistemdeki
Harmonic (gz-sim8) kaldırılmaz, ikisi yan yana durur.

**Neden:** TurtleBot 4 hazır RGB-D kamera, lidar ve sürüş sistemiyle geliyor. Harmonic'te
aracı, kamerayı ve lidarı elle tanımlamak Faz 3'e 1–2 hafta ekliyordu. Disk artık engel
değil (K-028).

**Bedeli:** İki sürüm yan yana. Fortress `ign`, Harmonic `gz` komutunu kullanıyor, ortam
değişkenleri (`IGN_*` / `GZ_*`) karışabilir. Simülasyon açılırken hangi sürümün çalıştığı
denetlenmeli. ~2 GB disk.

---

## K-028 · Disk engeli kalktı
**Tarih:** 2026-10-05 · **Durum:** Yürürlükte

Ubuntu bölümü (`nvme0n1p5`) 84 GB, 26 GB boş (2026-10-05, `df -h /`). Faz 3 (~2 GB) ve Faz 4
(Ollama modeli, ~4 GB) sığıyor. Ek temizlik yapılmadı.

**Neden:** Daha önce bölüm 60 GB ve 2,8 GB boştu, Faz 3'ten önce karar bekliyordu. Bölüm
büyütüldükten sonra bu karar gereksiz kaldı.

---

## K-029 · Kablo çekme testi: E5V beslemesi, süre kartın saatiyle
**Tarih:** 2026-10-05 · **Durum:** Yürürlükte

Ajan bağlantısının fiziksel kopması, kart ajan kablosundan değil **E5V'den** beslenirken
sınanır: JP5 [5-6], CP2102'nin +5V pini → CN7 pin 6 (UM2505 Tablo 4, Tablo 7, §7.4.1).
Açma sırası: önce CP2102 (LD3 yeşil), sonra CN1. Test `tools/unplug_test.py`.

Kopmadan sıfır hıza geçen süre **kartın saatiyle** ölçülür: son `HEARTBEAT_ACK`'in `ts_ms`'i
ile ilk `DRIVE`'ın `ts_ms`'i. Bilgisayarın ölçtüğü süre yalnızca bilgi içindir.

Testten sonra JP5 varsayılana (5V_STLK) döner, E5V teli çıkarılır. Faz 5'teki 10 tekrar
(K-015) için düzen bu maddeye bakılarak yeniden kurulur.

**Neden:** Nucleo varsayılan olarak ajan kablosundan beslenir, kablo çekilince kart da
kapanır ve kalp atışı kuralını işletemez. E5V düzeninde kart araç tarafından beslenir, gerçek
araca da daha çok benzer (kart aracın beslemesinden, ajan bilgisayarından değil).
Bilgisayarın saati iki USB köprüsünün gecikmesini de katıyor: aynı olayda kart 500 ms,
bilgisayar 569–605 ms ölçtü.

**Bedeli (sınırlılık):** Kablo **geri takılırken** kart yeniden başlıyor. Reset bayrakları
(`RCC_CSR`) okundu: JP3 takılıyken yalnızca `PINRSTF` (besleme ya da yazılım değil, reset
pini). JP3 çıkarılınca reset yine oluyor ve birikmiş bayraklarda `SFTRSTF` görüldü. Yorum:
ST-LINK açılırken işlemciyi resetliyor, JP3 yalnızca yolunu değiştiriyor (JP3'süz kısım
temiz ölçümle doğrulanmadı). Kart `HOLD`'da açıldığı için güvenli tarafa düşüyor, ama
geri takmadan sonra `HOLD` mandalı fiziksel testte gösterilemiyor (`decision_test.py`
yazılımla gösteriyor). Gerçek araçta ajan karta ST-LINK üzerinden bağlanmaz; bu
geliştirme kartına özgü.

---

## K-030 · ROS↔Harmonic köprü paketleri kaldırılır (K-027'ye ek)
**Tarih:** 2026-10-05 · **Durum:** Yürürlükte

TurtleBot 4 simülatörü için `ros-humble-ros-gzharmonic*` paketleri (6 adet) kaldırılır,
yerine Fortress'in `ros-humble-ros-gz-*` paketleri gelir. Gazebo Harmonic'in kendisi
(gz-sim8) kalır.

**Neden:** K-027 "Harmonic'le yan yana durur" diyordu. Gazebo'nun iki sürümü için doğru, ama
ROS köprü paketleri birbirini dışlıyor (`Conflicts: ros-humble-ros-gz-sim` …). Deneme
kurulumu (`apt-get -s`) bunu gösterdi. Bu 6 paketi sistemdeki başka paket kullanmıyor; tek
bir `apt install ros-humble-ros-gzharmonic` ile kurulmuşlardı.

**Bedeli:** ROS 2'den Harmonic'e bağlanan eski işler (vSLAM çalışması gibi) bu bilgisayarda
çalışmaz. Geri kurulursa TurtleBot 4 simülatörü kalkar.

---

## K-031 · Nav2'nin hız komutu Faz 3'te karttan geçer (asgari aktarma)
**Tarih:** 2026-10-05 · **Durum:** Yürürlükte

Faz 3'te kart `VELOCITY_CMD`'yi işler: `NORMAL`'de araç kanalına `DRIVE` olarak aynen
aktarır, `HOLD`'da aktarmaz (20 Hz sıfır hız sürer). Kırpma (LIMIT, RULES §3.2) Faz 4'te
kalır.

**Neden:** Faz 3'ün "bitti sayılır" ölçütü "kartın kablosu çekilince araç duruyor". Nav2
aracı doğrudan sürerse kart onu durduramaz. Hız yolu Nav2 → köprü → kart → köprü →
simülasyon olmalı. `VELOCITY_CMD` işleme Faz 4'e bırakılmıştı (STATUS "Sırada"); asgari
kısmı öne alındı.

**Bedeli:** Faz 3'te kart hız komutunu denetlemeden geçirir; yalnızca durum makinesi
(`HOLD`) ve kalp atışı korur.

---

## K-032 · Deney sahası: kendi açık saha dünyamız (`ika_saha`)
**Tarih:** 2026-10-05 · **Durum:** Yürürlükte

Faz 3–5'in simülasyon ortamı TurtleBot 4'ün hazır dünyaları (`warehouse`, `depot`, `maze`)
değil, sıfırdan yazılan bir açık saha: `ros2_ws/src/ika_sim/worlds/ika_saha.sdf`.

- **Boyut ve düzen:** 20 × 12 m, x −3…17, y −6…6. Beton bariyerlerle çevrili, doğuda
  ~3,9 m açık kapı (y −1,97…1,97). İçinde konteyner, kamyonet, çöp konteyneri. Planlanan
  3 yasak bölge: personel alanı, kazı alanı (başlangıçtan kapıya giden düz yolun üstünde),
  yakıt alanı. Taslak koordinatlar `docs/STATUS.md`'de.
- **Koordinat ilkesi:** Robot dünyanın (0, 0) noktasında, doğuya (yaw 0) bakarak başlar.
  RTAB-Map haritanın başlangıcını robotun ilk konumu kabul ettiği için dünya koordinatı =
  harita koordinatı. Kartın coğrafi sınırı doğrudan dünyanın tasarımından yazılabilir.
  Robotu başka bir açıyla başlatmak bu eşitliği bozar.
- **Yasak bölgeler yalnızca görsel** (`visual` var, `collision` yok): lidar ve fizik
  onları görmez, robot fiziksel olarak girebilir. Onu yalnızca kurallar durdurur (Nav2
  maskesi, kartın coğrafi sınırı). Deneyin ölçtüğü şey bu.
- **Dokular kendi betiğimizle** (`ika_sim/tools/gen_textures.py`, sabit tohum 2026):
  asfalt, konteyner, yasak bölge boyası, çöp konteyneri. Lisans yok, tekrarlanabilir,
  tekrar etmeyen desen (görsel haritalama için). PNG/JPG'ler depoda.
- **Hazır model (Gazebo Fuel) kuralı:** kullanmadan önce dosyasında `<static>`, çarpışma
  şeklinin basitliği ve malzeme türü (`materials/scripts` = eski tür) denetlenir. Yalnızca
  CC0 lisanslı modeller. Şu an: Jersey Barrier, Pickup.
- **Başlatma:** `ros2 launch ros2_ws/src/ika_sim/launch/ika_sim.launch.py`. TurtleBot 4'ün
  başlatma dosyası dünya arama yolunu (`IGN_GAZEBO_RESOURCE_PATH`) baştan yazdığı için onun
  `ignition.launch.py`'si bu dosyada tekrarlanır ve yola `worlds/` eklenir. `.sdf`'deki
  `<world name>` dosya adıyla aynı olmalı: ROS köprüleri konu adlarını ondan kurar.

**Neden:** Esra SDF'yi öğrenmek istedi. Ayrıca deney ortamı tamamen kontrol altında
olur: yasak bölgeler ve güvenli noktalar koordinatları bilinerek yerleştirilir, 3.2'deki
saha tanımı dünyanın tasarımından çıkar. Açık saha İKA temasına daha yakın.

**Bedeli:** Hazır dünyaya göre ~1–2 oturum iş. Açık sahada kamera için doku azdır; dokular
ve nesneler bunu telafi etmeli, 3.1'de haritalamayla sınanacak.

---

## K-033 · RTAB-Map kamera + lidar ile çalışır (plan belgesinden sapma)
**Tarih:** 2026-10-05 · **Durum:** Yürürlükte

Plan belgesi RTAB-Map'i yalnızca RGB-D (kamera) modunda istiyordu. Faz 3.1'de kamera +
lidar kullanılır (`subscribe_scan:=true`, `scan_topic:=/scan`).

**Neden:** Kamera konum tanıma ve döngü kapatma için, lidar Nav2'nin kullanacağı 2D engel
haritası için. TurtleBot 4 simülatörünün kamerası 320×240; derinlikten üretilen 2D harita
gürültülü olabilir.

**Bedeli:** vSLAM çalışmasındaki salt kamera düzeninden ayrılır; tezde gerekçesiyle yazılır.

---

## K-034 · Faz 3 aracı: ORINIUM İKA modeli (K-027'nin araç kısmını değiştirir)
**Tarih:** 2026-10-06 · **Durum:** Yürürlükte

Faz 3–5 simülasyonunda araç TurtleBot 4 değil, ORINIUM takımının İKA modeli
(`ika_arac`, SolidWorks çıktısı `URDF_icin.SLDASM`). Simülatör Gazebo Fortress kalır
(K-027'nin simülatör kısmı geçerli).

- **Kaynak ve port:** `~/Documents/ORINIUM/ugv_telemetry_new/sim/models/ika_arac/`,
  Harmonic için yazılmış. Depoya `ros2_ws/src/ika_sim/models/ika_arac/` olarak Fortress'e
  çevrilmiş hâli alınır. Üç değişiklik: SDF 1.11 → 1.9, mesh yolları `model://`, eklenti
  adları `gz-sim-*` → `ignition-gazebo-*`. Kaynak ve takım tezde belirtilir.
- **Araç:** gövde 1,51 × 1,15 m, 6 salıncakta 12 tekerlek, DiffDrive (`/cmd_vel`, `/odom`),
  lidar (`/scan`, 720 örnek, 8 m, 10 Hz), RGB-D kamera (`/camera/image`,
  `/camera/depth_image`, 640×480, 10 Hz), IMU (`/imu`), kule kamerası.
- **Saha (K-032) araca göre genişletilir:** geçitler ~3 m. Koordinat ilkesi (araç (0, 0)'da
  doğuya bakarak başlar) aynen kalır. Şarj istasyonu yok.
- **Elle kurulacaklar:** spawn, ROS köprüsü (`ros_gz_bridge`), `tf`. TurtleBot 4'ün hazır
  parçalarının yerine geçer.

**Neden:** Esra gerçekçi bir İKA görünümü istedi. Ölçüm de lehine çıktı (2026-10-06,
`ika_saha`'nın kopyası, 2 × 20 s): İKA ile hız oranı **%100**, TurtleBot 4 ile %46. İKA
ölçümünde ROS köprüleri yoktu, sonuç biraz iyimser. Boş dünyada lidar, kamera ve sürüş
doğrulandı.

**Bedeli:** Sahanın Blok 2–5 koordinatları yeniden yazılır. Köprü ve `tf` işi gelir.
Dönüşte odometri %14 fazla sayıyor (12 tekerleğin kayması). Bu, RTAB-Map'in düzelteceği
hata, tezde yazılır. K-033'teki "kamera 320×240" gerekçesi artık geçersiz (kamera
640×480), lidar kullanma kararı yine geçerli. Model takımın ortak işi: kaynağı belirtilir,
takımdan onay alınır.

---

## K-035 · Deney sahası İKA'ya göre 32 × 20 m (K-032'ye ek)
**Tarih:** 2026-10-06 · **Durum:** Yürürlükte

K-032'deki 20 × 12 m saha İKA (K-034) için 32 × 20 m'ye büyütülür: x −3…29, y −10…10,
doğuda kapı y −1,97…1,97. Kenarlar 4'ün katı, Jersey Barrier (4,065 m) 4 m arayla tam
oturur (25 bariyer). Nesneler gerçek boyutlarında, aralarındaki geçitler ≥ 3 m. Yasak
bölgeler: personel x 3…9, y −8,2…−4,5; kazı x 13…16, y −1,5…1,5; yakıt x 17…23,
y −8,2…−4,5. Koordinat ilkesi ve "yasak bölgeler yalnızca visual" kuralı aynen geçerli.

**Neden:** Araç 1,78 × 1,15 m, yerinde dönerken ~2,3 m çaplı alan ister, Nav2 bir de
güvenlik payı bırakır. 30 × 18 m bariyer ölçüsüne oturmadı: üst üste binen bariyerler
titrer, köşede 1,6 m'lik delik kalır. Lidar 8 m'ye kadar görüyor, ama sahanın ortasındaki
konteyner ve koniler sayesinde her noktadan bir nesne görünür.

**Bedeli:** Dokular yeniden üretildi (henüz harita olmadığı için kayıp yok). Bariyer
sayısı 15'ten 25'e çıktı. TurtleBot 4 ile hız ~%44, değişmedi.

---

## K-036 · İlk harita kabul edilir, 3.2'de ≥ 1 m güvenlik payı (K-032'ye ek)
**Tarih:** 2026-10-06 · **Durum:** Yürürlükte

3.1'in ilk haritası (`ros2_ws/src/ika_nav/maps/ika_saha.pgm`/`.yaml`) Nav2 ve 3.2 için
kullanılır. K-032'nin "harita koordinatı = dünya koordinatı" varsayımı ölçüldü: harita
başlangıç etrafında ~2° dönmüş, hata uzak uçta en çok ~0,8 m (konteyner +0,55 m x,
−0,25 m y; tanklar 0,7–0,8 m güneyde). 3.2'de yasak bölgeler ve izinli alan dünya
koordinatından yazılırken en az 1 m güvenlik payı bırakılır.

**Neden:** Haritanın şekli ve boyutları doğru, hata ölçülmüş ve sınırlı. Yeniden
haritalama yerine pay bırakmak Esra'nın tercihi.

**Bedeli:** İzinli alan küçülür, yasak bölgeler büyür; dar geçitler (güney koridoru 3 m)
daralır. Hata tezde ölçüm olarak yazılır. Haritalama tekrarlanırsa hata yeniden ölçülmeli.

---

## K-037 · Saha tek dosyada (`shared/site/ika_saha.yaml`), Nav2'de konum AMCL ile
**Tarih:** 2026-10-07 · **Durum:** Yürürlükte

- **Saha tanımı:** izinli alan, yasak bölgeler (gerçek sınırlar), `home` ve adlı güvenli
  noktalar `shared/site/ika_saha.yaml`'da, dünya = harita çerçevesinde, metre.
  `tools/gen_site.py` payı (`margin_m`, K-036) uygular, veriyi denetler ve kartın
  `site_data.c`'sini ve Nav2'nin keepout maskesini üretir. Maske kartın kuralıyla
  hesaplanır: izinli alanın dışı da kapalıdır. Yuvarlama güvenli tarafa yapılır.
- **Konum bulma:** Nav2 ile gezinirken AMCL, depodaki `ika_saha.pgm` ve lidar.
  RTAB-Map yalnızca haritalamada kullanıldı. Başlangıç konumu (0, 0, doğu) başlatma
  dosyasında verilir.
- **Payın sonucu:** güney koridoru kapanır, kazı yalnızca kuzeyden dolanılır
  (Esra'nın kararı).

**Neden:** Kart ve Nav2 aynı bölgeleri tek kaynaktan alır (bir kavram tek yerde).
Testler maskenin her hücresini (314 622) kartın gerçek C koduyla karşılaştırıyor, fark 0.
AMCL'de harita depoda, tekrarlanabilir. Keepout maskesiyle aynı ızgarayı kullanıyor.

**Bedeli:** Haritanın 2°'lik dönmesi yüzünden kuzeydoğu köşesinde haritadaki bariyer
izinli alanın ~0,25 m içinde: kart orada ulaşılamayacak bir hedefi kabul edebilir
(Nav2 reddeder, güvenlik açısından zararsız). Hata en uzak köşede ~1,2 m. Konum
yalnızca lidarla bulunur, kamera gezinmede kullanılmaz.

---

## K-038 · Nav2 düzeni: costmap'lerde lidar katmanı yok, keepout bir katman, ize 0,3 m pay
**Tarih:** 2026-10-07 · **Durum:** Yürürlükte

`ros2_ws/src/ika_nav/config/nav2_params.yaml`:
- **İki costmap'te de katmanlar:** statik harita → keepout (maskeyi okuyan ikinci `StaticLayer`)
  → şişirme (1,5 m). Lidar katmanı (`obstacle_layer`) **yok**. `use_maximum: true` costmap
  düzeyinde: harita ile keepout birleşir, biri ötekini ezmez.
- **Araç izi:** 1,78 × 1,15 m, her yönde `footprint_padding` 0,3 m.
- **Ara katman:** CycloneDDS (`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`, `~/.bashrc`).

**Neden:**
- **Lidar katmanı:** lidar katmanı olan costmap'in tf tamponu yük altında (RViz ekranları,
  costmap aboneliği) 75–190 s içinde kalıcı olarak donuyordu; controller bayat konumla "vardım"
  diyor ya da yanlış yöne sürüyordu. Aynı yük altında lidar katmanı olmayan costmap donmadı
  (Deney A, STATUS). Mekanizma kanıtlanmadı. Sahadaki engellerin hepsi sabit ve haritada.
- **Keepout katman:** Nav2'de filtreler şişirmeden sonra uygulanıyor; planlayıcı aracı yasak
  bölgenin dibinden geçirmeye çalıştı. Katman olunca yasak bölgeler de şişirilir.
- **Pay:** harita konteyner civarında ~0,5 m kaymış (K-036), AMCL ~0,3 m yanılıyor ve lidar
  katmanı yok. Pay olmadan planlayıcı konteyner ile kazı arasındaki 1,24 m'lik darboğazı seçti,
  araç gerçek konteynere sürtündü. Payla darboğaz kapalı, diğer geçitler (≥ 3,9 m) açık.
- **CycloneDDS:** tf donmasının sebebi sanıldı, değildi. Nav2'nin Humble için önerdiği ara
  katman, zararsız; kalıyor (Esra'nın kararı).

**Bedeli:**
- Nav2 haritada olmayan yeni engeli görmez (hareketli engelden kaçınma kapsam dışı). Bu,
  tezde kartın varlık nedenini destekleyen bir gözlem: planlayıcının kendi güvenlik önlemleri
  altındaki katman bozulunca sessizce devre dışı kaldı; kart bu katmandan bağımsız.
- Araç engellere ve yasak bölgelere en az 0,875 m (iç yarıçap) yaklaşır; dar yerlerde temkinli.
- Haritanın 2°'lik dönmesi uzak uçta Nav2'nin konumunu gerçekten ~1,4 m ayırıyor (deneme 2).

## K-039 · Hız ve ivme limitleri İKA'ya göre yeniden kurulacak (RULES §1)
**Tarih:** 2026-10-08 · **Durum:** Yürürlükte (doğrusal ivme ölçülecek)

RULES §1'deki tablo TurtleBot 4 / Create 3'e göre yazılmıştı; araç artık İKA (K-034) ve
Nav2'ye 0,5 m/s verildi, bekçi 0,30 m/s'de kaldı (sıralama ters). Karar: Nav2 indirilmez,
**tablo İKA'ya göre yeniden kurulur**. K-012'nin ilkesi aynen geçerli: Nav2 < bekçi < platform
tavanı. İlk adım İKA modelinin gerçek tavanını bulmak; kesin değerler ve kart sabitleri o
zaman yazılır.

**Neden:** Nav2'yi indirmek çelişkiyi kapatır ama tablo var olmayan bir aracı anlatmaya devam
ederdi; tezde sınırların gerekçesi bugünkü araca dayanmalı. Bedel: RULES, kart sabitleri,
testler değişir, karta yeniden yükleme gerekir.

**Değerler (2026-10-08, RULES §1):** bekçi 0,6 m/s · 0,6 rad/s · 1,2 rad/s² (Nav2'nin 1,2
katı); İKA tavanı 3,6 m/s (KTR Tablo-3, 13 km/h) · ~7 rad/s (ω = 2v / 1,02 m). Doğrusal ivme:
Nav2'de sınır olmadığı için Faz 4'ten önce `/cmd_vel` kaydından ölçülecek. KTR'de 15 ve
30 km/h de geçiyor; resmî tablo esas alındı. **Düzeltme:** kartta henüz limit sabiti yok
(kırpma Faz 4'te), bu adımda karta yükleme gerekmedi. Bağlı sonuçlar: §3.4 toleransı
v_max = 0,60 ile, §5'te kalp atışı kaybında en fazla 30 cm.

## K-040 · 3.3 köprü tasarımı (protocol §10, K-031)
**Tarih:** 2026-10-08 · **Durum:** Yürürlükte

1. **Nav2 karttan kaçamaz:** `bt_navigator` `/goal_pose`'u dinlemez; hedef Nav2'ye yalnız
   kartın `GOAL`'ı gelince `NavigateToPose` ile verilir. Nav2 hızı `/cmd_vel_nav`'a yayımlar;
   `/cmd_vel`'e yalnız köprünün araç tarafı (`DRIVE`) yazar.
2. **İki düğüm:** `agent_bridge` (GOTO_CMD, VELOCITY_CMD, HEARTBEAT, VERDICT → `/guard/verdict`)
   ve `vehicle_bridge` (GOAL, DRIVE, TELEMETRY 20 Hz).
3. **`Link` ortak pakette:** `tools/link_test.py`'deki `Link`,
   `shared/protocol/python/ika_protocol/link.py`'ye taşınır; testler ve köprü aynı kodu kullanır.
4. **TELEMETRY kaynağı AMCL'nin `map → base_link`'i**, `odom` değil.

**Neden:** (1) Kartı atlayan bir yol açık kalırsa bekçi hiçbir şeyi engelleyemez, tezin ana
iddiası çöker. (2) Deney yapılandırmalarında (K-005: A–D) yalnız ajan tarafı değişir; araç
tarafı bir kez yazılıp sabit kalır. (3) Bir kavram tek yerde; testler köprünün gerçek kodunu
sınar. (4) Saha harita çerçevesinde tanımlı; odometri zamanla kayar. AMCL sıçramalarının
tutarlılık toleransında (RULES §3.4) kaldığı denemede ölçülecek.

## K-041 · Nav2'ye çarpışma bekçisi (collision_monitor, approach)
**Tarih:** 2026-10-08 · **Durum:** Yürürlükte

Hız yolu: controller ve behavior → `/cmd_vel_raw` → `collision_monitor` → `/cmd_vel_nav` →
kart (`ros2_ws/src/ika_nav`). Tür `approach`: aracın izi (yerel costmap'in yayımladığı, 0,3 m
payla) gelen hızla 1 s ileri simüle edilir, çarpışacaksa hız kısılır. Kaynak `/scan`.

**Neden:** Araç engele dayanınca tekerlekler boşa döner, odometri ilerleme sayar (60 s'de 15 m),
AMCL metrelerce kopar (5,7–14 m); kart konumu AMCL'den aldığı için (K-040) o da yanılır.
2026-10-08'de araç böyle personel yasak bölgesine girdi. AMCL ayarı çözmedi: `alpha3` 0,8 ile
5,5 m, `recovery_alpha` ile 5,6–5,8 m. Monitörle aynı denemede araç konteynere 0,36–0,58 m
kala durdu, AMCL hatası ≤ 0,17 m (`tools/amcl_push_bench.py`). Normal gezinmeye karışmadı
(konteynerin arkasındaki dar yol dahil). `stop`/`slowdown` seçilmedi: her yöne durdurur, araç
engelin dibinde kalıcı kilitlenir; `approach` yöne duyarlı.

**Sınır:** Monitör Nav2'nin parçasıdır, kartın bağımsız katmanının yerini tutmaz; hızı yalnız
azaltabilir, kartı atlatamaz. Haritada olmayan engelden kaçınma yine kapsam dışı (K-038).
Kök neden (odometri patinajı görmüyor) duruyor; lidar odometrisi ya da EKF ileride ele alınabilir.
