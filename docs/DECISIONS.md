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
