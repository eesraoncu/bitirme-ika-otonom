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
