# Proje Durumu

> Bu dosya her çalışma oturumunun **başında okunur**, **sonunda güncellenir**.
> Claude Code ile çalışırken ilk iş: bu dosyayı ve `docs/DECISIONS.md`'yi okut.

**Son güncelleme:** 2026-10-14
**Bulunduğumuz faz:** **Faz 4**: 4.0 ve 4.1 bitti (2026-10-14, `v0.3.1`), sırada 4.2 köprü ve 4.3 ajan. Faz 3 bitti (`v0.3.0`): 3.0–3.2 bitti (K-032…K-038). Hız limitleri İKA'ya göre (K-039). **3.3 köprü bitti** (K-040): RViz hedefi ve Nav2 hızları karttan geçiyor, yasak hedef reddediliyor, kablo çekilince araç duruyor, köprü yeniden bağlanıyor. Açık: AMCL kaybı (aşağıda)

---

## Şu an ne yapılıyor

**2026-10-13: Faz 4 planı onaylandı** (Esra'yla). Bitti sayılır (plan belgesi): doğal dille
verilen görev ("depo arkasına git, orada 30 saniye bekle") baştan sona kart üzerinden çalışıyor;
hatalı komut reddedilince ajan gerekçeyi kullanıp kendini düzeltiyor. Sıra en belirsiz işten başlar:

**Sırada:**
1. **4.0 Hazırlık ve model seçimi:** bekçinin doğrusal ivmesi (Nav2 `/cmd_vel` kaydından);
   NVIDIA sürücüsü (RTX 3050 `lspci`'de görünüyor, `nvidia-smi` yok; `sudo` komutlarını Esra
   çalıştırır); Ollama; model seçimi (araç çağırma şart, ~4 GB VRAM), sıcaklık sabit ve kayıtlı.
   Yerel model yetmezse B planı: API.
   **İlerleme (2026-10-13):**
   - NVIDIA `nvidia-driver-595-open` kuruldu (595.99.02; Secure Boot açık, MOK kaydı yapıldı).
     `prime-select` on-demand: masaüstü Intel'de, NVIDIA isteyen programda. `nouveau` artık yüklü değil.
   - Ollama 0.40.3 kuruldu (resmî betik; sürücü önceden kurulu olduğu için CUDA deposu eklenmedi),
     servis açılışta başlıyor. `inference compute`: `library=CUDA`, **kullanılabilir 3,6 GiB**.
   - Aday araştırması (Türkçe araç çağırma kıyaslaması yok, kendimiz ölçtük). Elenen: gemma4
     (en küçüğü 4,3 GB), ministral-3, llama3.2, tev1 (karar modeli), 8B+.
   - `tools/llm_select_bench.py`: 14 Türkçe cümle (yer adı, koordinat, bekle, hız, dur, bileşik,
     iki ret-düzeltme), ilk araç çağrısı puanlanır. Sıcaklık 0, seed 42, `num_ctx` 4096, 3 tekrar:

     | Model | Doğru | Hata | Medyan | En uzun | GPU |
     |---|---|---|---|---|---|
     | granite4.1:3b | 39/42 | 3 yanlış arg. ("iki dakika" → 2 s) | 0,38 s | 0,64 s | %100 |
     | qwen3.5:4b | 39/42 | 3 yanlış arg. (coğrafi retten sonra aynı komutu tekrar) | 1,91 s | 4,55 s | %69 |
     | qwen3.5:2b | 36/42 | 6 çağrı yok (iki retten sonra yalnız metin) | 0,70 s | 1,19 s | %92 |
     | phi4-mini | 0/42 | 42 çağrı yok (çağrıyı metne yazıyor) | 1,30 s | 6,51 s | %86 |

     İki ret-düzeltme cümlesini yalnız granite doğru yaptı. phi4-mini elendi ve silindi.
     Test küçüktü (14 bağımsız örnek), genişletildi:
   - **Genişletilmiş test** (31 cümle: yer 7, koordinat 4, birim 7, dur 2, bileşik 3, ret 8 = 5 GEOFENCE
     ipucu `gen_site.nearest_safe`'ten + 3 LIMIT; `--temperature`, `--seeds`):

     | Model | Sıcaklık 0 | ret | 0,7 × 5 seed | ret | kararsız cümle | Medyan | En uzun |
     |---|---|---|---|---|---|---|---|
     | granite4.1:3b | 27/31 | 8/8 | 127/155 | 37/40 | 4 | 0,39 s | 1,18 s |
     | qwen3.5:4b | 30/31 | 8/8 | 138/155 | 35/40 | 11 | 1,80 s | 8,22 s |
     | qwen3.5:2b | 22/31 | 1/8 | 100/155 | 4/40 | 11 | 0,72 s | 2,03 s |

     granite hataları sistematik (dakika → saniye yok; "konteynerin önü" → `konteyner_arkasi`),
     qwen3.5:4b'ninki rastgele (0,7'de `stop`, `bur` gibi uydurma araçlar).
   - **Model seçildi: `granite4.1:3b` (K-045).** qwen3.5:2b silindi, qwen3.5:4b yedek. Boş disk 13 GB.
   - **4.2'ye not:** ilk testte qwen3.5:4b ipucu yalnız adken (`"konteyner_onu"`) aynı reddedilmiş komutu
     tekrarladı, ad + koordinat verilince düzeltti (tek örnek, kanıt değil). Gerekçe ajana ad + koordinat
     ile verilsin.
   - **4.3'e not:** granite'in birim hatası araç tanımı/istemle denenecek (ör. `bekle`'de dakika).
   - **İvme ölçümü bitti → K-046 (2026-10-14), 4.0 BİTTİ.** `tools/nav2_accel_bench.py`: hedefler
     /goal_pose'tan (karttan geçerek), `/cmd_vel_raw`, `/cmd_vel_smoothed`, `/cmd_vel_nav` kaydı; kart
     bağlı, NORMAL (kırpma yok, komutlar aynen geçiyor). Rota güvenli noktalar değil, iz hesabıyla
     temiz açık alan noktaları (aşağıdaki bulgu): (0,0) → (13,−5,5) → (24,−0,5) → (10,0) → (2,0,5).

     | Tur | Nav2 | Sonuç | Hızlanma adımı v / ω | collision ahead |
     |---|---|---|---|---|
     | 1 | yumuşatıcısız, güvenli noktalar | konteyner_arkasi'nda vazgeçti | 0,5 / 0,55 | 128 |
     | 2 | yumuşatıcısız | 4/4 | 0,5 (10 m/s²) / 0,72 | 21 |
     | 3 | yumuşatıcı, yavaşlama −1,0 | 1. hedefte vazgeçti (12 cm kayıp keepout'a girdi) | 0,025 / 0,05 | 97 |
     | 4 | yumuşatıcı, yavaşlama sınırsız | **4/4** | **0,025 / 0,05** (işaret değişimi hariç) | **0** |

     Doğrulananlar: çıkış sabit 20 Hz (aralık ≤ 52 ms; yumuşatıcısız kurtarmalar 10 Hz geliyordu);
     yol takibinde |ω| en çok 0,556 < 0,6; tipik ivme (%99) ~0,6 m/s². Tur 4'te neden hiç collision
     ahead olmadığı açıklanmadı (2026-10-14 sonrası: tesadüf, aşağıda).
   - **~~AÇIK~~ ÇÖZÜLDÜ (d1, aşağıda): güvenli noktaların bir kısmına Nav2 ulaşamıyordu.** İz (+0,3 pay)
     harita ve keepout maskesiyle karşılaştırıldı: `baslangic`, `kapi_onu` temiz; `konteyner_arkasi`
     (8; 7,6) paylı kuzey sınırına (y 8,59) 0°'de 12 cm, 10°'de değiyor (tur 1'in nedeni);
     `kuzeybati` (1, 6) 0°'de haritadaki engele değiyor, 75°'de temiz; `konteyner_onu` (8, 2)
     hiçbir yönde temiz değil (konteyner). RECOVERY bu noktalara gönderirse kart takılır.
     Noktalar yeniden seçilecek + ulaşılabilirlik denetimi (saha üreteci mi Nav2 mi: iki klasöre
     dokunuyor, tasarımı o adımda konuşulacak). Karta yükleme gerekecek (`site_data.c`).
   - **4.1 sırası değişti (Esra, 2026-10-14): önce 4.1d RECOVERY,** üç parçada: d1 güvenli noktalar +
     ulaşılabilirlik testi · d2 kart durum makinesi · d3 yükleme + uçtan uca. Yeni geçiş (K-047, d2'de
     yazılacak): RECOVERY'de telemetri 500 ms gelmezse → HOLD. 180 s süre sınırı **eklenmedi** (Esra):
     bilinen sınır, Nav2 kurtarma hedefinde vazgeçerse kart RECOVERY'de kalır (çıkış: kalp atışı kaybı).
   - **d1 bitti (2026-10-14):** güvenli noktalar yeniden seçildi (ölçüt: izin + payın dönüş yarıçapı
     1,559 m içinde harita engeli ve keepout yok): baslangic (0, 0) · kuzeybati (1,75; 6) ·
     konteyner_onu (8,5; 1) · kapi_onu (26, 0) · ~~guney (13; −5,5)~~ (aynı gün çıkarıldı, aşağıda) ·
     konteyner_arkasi çıkarıldı
     (kuzey koridorunda 4 m içinde uygun yer yok). `shared/site/tests/test_safe_points.py`: iz/pay
     nav2_params'tan, harita ve maske ika_nav/maps'ten okunur; eski noktalarla 3'ünü yakaladı.
     `site_data.c` yeniden üretildi (maske değişmedi), **karta henüz yüklenmedi (d3)**. Testler: site 24,
     kart 65, köprü 25. **4.3'e not:** `llm_select_bench.py`'deki "Konteynerin arkasına git" cümlesi artık
     olmayan yeri bekliyor (K-045 sonuçları eski noktalarla, geçerli); ajan için `places` anahtarı
     açılınca betik oradan okusun.
   - **d2 + d3 bitti (2026-10-14), 4.1d BİTTİ:** `firmware/app/recovery/` (5 ret, varış 35 cm,
     telemetri 500 ms, süre 180 s; K-047), `guard`: `guard_telemetry` (araç konumunun coğrafi sınırı,
     varış), `guard_tick` (zaman kuralları), RECOVERY'de hız geçer. PC: 77 test, kasıtlı 6 hatanın 6'sı
     yakalandı. Kart: flash 40 576 B, 0 uyarı, yüklendi ve doğrulandı; `link_test` ve `decision_test`
     (yeni: yasak bölgede araç → RECOVERY_SAFE + varış, telemetri kesilince 513–515 ms'de HOLD, 5 ret →
     RECOVERY_HOME + varış) 4 çalıştırmada hepsi geçti. Uçtan uca (simülasyon, kart, köprü):
     - A: araç (8,5; 1) → 5 yasak hedef → 4 s'de RECOVERY + GOAL (0,0) RECOVERY_HOME → 24 s sonra
       varış, HOLD.
     - B: araç kazı köşesinde (11,7; −3,05) → RECOVERY → Nav2 12 s'de vazgeçti (araç kıpırdamadı) →
       kart tam 180 s'de HOLD. Süre sınırı yokken (sabah, d2 yazılımı) kart süresiz RECOVERY'de kaldı.
     - Test hatası düzeltildi: `decision_test`'in durum okuması tampondaki eski HEARTBEAT_ACK'i
       okuyordu (kart doğruydu).
   - **Nav2 kazı köşesinde takılması: nedeni bulundu, guney güvenli noktalardan çıkarıldı (Esra, A).**
     Planlayıcı (NavFn) yalnız merkeze bakıyor, yol keepout'a 1,04 m yaklaşıyor (10,96; −3,05), izin
     dönüş yarıçapı 1,56 m. guney bölgesinin tek girişi personel köşesi (10; −3,5) ile kazı köşesi
     (12; −2,5) arasındaki 2,24 m'lik çapraz boğaz (paylarla; gerçekte ~5 m: kartın 1 m'si K-036 +
     Nav2'nin 0,3 m'si K-038 aynı harita hatası için üst üste). Araç boğazda dönünce izi keepout'a
     giriyor, sonra her hareket (ileri, spin, backup) "collision ahead": 4 denemenin 2'si takıldı.
     Tur 4'teki başarı tesadüftü (K-046'nın yavaşlama gerekçesi yine geçerli). guney çıkarıldı:
     4 güvenli nokta, `site_data.c` karta yüklendi, `link_test` + `decision_test` geçti (kazı ortası
     ipucu artık konteyner_onu). **Sahanın bilinen sınırı:** personel–yakıt arası (kazının güneyi)
     Nav2 için zor bölge; `nav2_accel_bench.py` turunun 1. bacağı (13; −5,5) da oradan geçiyor.
     Kalan seçenekler (seçilmedi): iz payını küçültmek (K-038 yeniden), Smac Hybrid-A*.
     test_safe_points noktanın kendisini denetliyor, noktaya giden yolu değil.
   - **4.1b bitti (2026-10-14, K-048, K-042 uygulandı):** kart: `guard_wait` (WAIT → HALT(süre), NORMAL
     dışında MODE), `guard_stop` (her durumda kabul, HALT(0); RECOVERY'de → HOLD; ret serisini
     sıfırlamaz), HOLD'a her girişte tek HALT(0) (`enter_hold` + `guard_take_halt`). `vehicle_bridge`:
     HALT'ta, kanal kopunca, kart yeniden başlayınca Nav2 hedefini iptal (kabulden önce gelen iptal de
     yakalanır). PC: 86 test, kasıtlı 4 hatanın 4'ü yakalandı. Kart: 41 276 B, 0 uyarı; `decision_test`
     2/2 (HALT(30), HALT(0), kalp atışında tek HALT 525 ms, varışta HALT, RECOVERY'de STOP → HOLD).
     Uçtan uca: yoldayken ajan köprüsü kapandı → 0,61 s'de Nav2 hedefi iptal, araç durdu (5 s'de 0 cm);
     yeniden bağlanıp SIFIRLA → araç 15 s kıpırdamadı, Nav2'de açık hedef yok. (A'daki açık hedef sorunu
     kapandı.) Ajanın WAIT/STOP göndermesi 4.2/4.3'te (ajan köprüsünde henüz arayüz yok).
   - **4.1a bitti (2026-10-14):** `firmware/app/rules/limits/` (`limit_axis`: yalnız hızlanma, adım
     30 mm/s · 60 mrad/s, ±600; `limit_speed_cmd`: 0 < değer ≤ 600). `guard_velocity` kırpıyor (son
     GÖNDERİLEN komuta göre, HOLD'da 0), NORMAL ve RECOVERY'de; `STATUS.clipped` sayılıyor. **K-031'in
     asgari aktarması bitti.** `guard_speed_limit`: MODE → LIMIT (VERDICT'te istenen, 1–600), ret içerik
     reddi (seri, 5'te kurtarma), kabulde SPEED_LIMIT_SET; `vehicle_bridge` bunu Nav2'nin `/speed_limit`'ine
     (m/s) yayımlar. Ajan köprüsünün günlüğünde "kırpılan hız". PC: 99 test, kasıtlı 4 hatanın 4'ü
     yakalandı. Kart: 42 104 B, 0 uyarı; `decision_test` 2/2 (ilk çalıştırmada iki test beklentisi yanlıştı:
     ω rampası ve 3+2 retle kurtarmanın başlaması, kart doğruydu). Uçtan uca: (0,0) → konteyner_onu →
     (0,0), 903 VELOCITY_CMD, **0 kırpma**.
   - **4.1c bitti (2026-10-14):** PC: `Link` her HEARTBEAT_ACK'ta eşitleme örneği alır, son 10'dan en
     küçük RTT'li (protocol §6.2; önceden yalnız HELLO'dan tahmin ediliyordu, saat kayınca 200 ms eşiği
     meşru komutları reddederdi). Kart: `rules/freshness` (−50…200 ms, saat taşmasında doğru),
     `guard_fresh` ajan kanalının her imzalı çerçevesinde REPLAY'den sonra: görev komutu ve SIFIRLA'ya
     FRESHNESS VERDICT'i (yaş, −50, 200), hız ve kalp atışı sessizce düşer, `err_fresh` sayılır, ret
     serisine girmez. Ajan köprüsü günlüğünde "bayat" ve "saat RTT". PC: 117 test, 4 hata denemesi
     yakalandı (biri doğru kodla eşdeğer çıktı, gerçek taşma hatasıyla yeniden). Kart: 42 440 B, 0 uyarı;
     `link_test`, `decision_test` 2/2 (RTT 11 ms; −500 ms → 505–507, +200 ms → −192). Uçtan uca: 897
     komutta 0 bayat, 0 kırpma, RTT 7 ms.
   - **4.1e bitti (2026-10-14, K-049) → 4.1 BİTTİ, kartın bütün kuralları çalışıyor (`v0.3.1`):**
     `rules/consistency` (tol = 25 cm + 0,6 m/s × Δt, −50 ms ≤ Δt ≤ 5 s, telemetri ≤ 500 ms); GOTO
     (GEOFENCE'ten sonra), WAIT, hiz_siniri (LIMIT'ten sonra), STOP'ta yok; içerik reddi. `guard_tick`
     döngünün başına alındı (zaman ve telemetri yaşı komutlardan önce). Ajan köprüsü RViz hedeflerinde
     inancı TF'ten doldurur. RULES §3.4'ün sayıları v_max 0,30 ile kalmıştı, düzeltildi. PC: 131 test,
     kasıtlı 4 hatanın 4'ü yakalandı. Kart: 43 868 B, 0 uyarı; `decision_test` baştan düzenlendi (bütün
     görev komutları telemetriyle tutarlı inançla; yeni TOO_FAR 300/25 cm, BELIEF_TOO_OLD 6009 ms,
     NO_TELEMETRY 754 ms), 2/2. Uçtan uca: RViz yolundan iki hedef kabul, vardı; seri 0, bayat ve kırpma
     artmadı, RTT 8 ms.
   - **4.2 bitti (2026-10-14, K-050):** `agent_bridge`: `/guard/task` (JSON: id, cmd git/bekle/hiz_siniri/dur,
     m/rad/s, inanç {x, y, stamp ROS}; dur dışında inanç şart) → GOTO/WAIT/SPEED_LIMIT/STOP; inancın
     zamanı kartın saatine (`ros_to_board_ms`); kararı `/guard/feedback` {id, accepted, text}; hatalı
     görev karta gitmez, id'siyle hata metni döner; bağlantı koparsa bekleyen görevlere "karar
     alınamadı". `feedback` parametresi full (D) / minimal (C); `/guard/verdict` her zaman tam.
     Türkçe gerekçe metni her reason için, coğrafi sınır ipucu güvenli noktanın adıyla
     (`convert.feedback_text`). Köprü birim testleri 59 (34 yeni). Uçtan uca (kart + simülasyon):
     D'de kabul, GEOFENCE ("konteyner_onu (8,50; 1,00)"), LIMIT, CONSISTENCY metinleri; hatalı JSON
     karta gitmedi; hiz_siniri → /speed_limit 0,3; C'de ajan yalnız "Komut reddedildi." gördü,
     /guard/verdict tam kaldı. `messages.yaml` yorumu ve protocol §7.1: BELIEF_TOO_OLD hi 5000
     (şema özeti değişmedi, kart yeniden yüklenmedi).
   - **4.3 bitti (2026-10-14, K-051):** `ros2_ws/src/llm_agent/agent_core.py` (araç tanımları + istem, tek
     kaynak; döngü: inanç modelden önce okunan konum, her adım tek araç, en çok 3 ret, metinle bitiş)
     ve `agent_node.py` (/agent/task → /guard/task, varış Nav2'den, bekle süreyle, /agent/log JSON).
     `ika_saha.yaml`'a `places` (konteyner_arkasi (11; 7) 0°, kazi_bati (9; −0,5) 0°, kazi_dogu
     (20; −0,5) 180°, kazi_kuzeyi (15; 5) 180°, yakit_kuzeyi (22; −2) 0°; gen_site doğrular, site
     testi iz/yön; site_data.c değişmedi). `llm_select_bench` ajanın tanımlarını ve köprünün gerçek
     gerekçe metnini kullanıyor: granite 30/31 (sıcaklık 0), 150/155 (0,7 × 5); birim 7/7, ret 8/8 ve
     40/40; tek hata "konteynerin önü" → konteyner_arkasi. Birim testleri 11, kasıtlı 3 hata yakalandı.
     **Uçtan uca (plan ölçütü sağlandı):** "Kapı önüne git, orada 30 saniye bekle." → git(kapi_onu)
     kabul, vardı → bekle(30) kabul → özet; 2 adım, 0 ret. "Kazı alanının ortasına git." → kart
     GEOFENCE ile reddetti (ipucu konteyner_onu (8,50; 1,00)) → model git(8,5; 1) → kabul, vardı;
     1 ret, tek denemede düzeltti. Model kararı 0,4–0,65 s.
     **Sırada: 4.4** birkaç deneme daha (C yapılandırması, hiz_siniri/dur, belirsiz talimat), sonuçlar
     buraya, sonra `v0.4.0` (Esra, 2026-10-14).
   - **Ağ:** okul Wi-Fi'si (GSBWIFI) IP'yi ara ara kaybediyor; o an ROS (CycloneDDS) ve Gazebo
     multicast'i kopuyor, süreçler toparlanmıyor. Kendi bağlantıyla sorun yok. Port 22 orada kapalı.
   - **Teşhis düzeltmesi:** "collision ahead ← AMCL kaybı" (aşağıda, 3.3) yanlıştı: tur 1'de AMCL
     0,2 m doğruyken de oldu. Neden: paylı iz keepout'a değiyor (planlayıcı yalnız merkeze bakıyor,
     RPP izin tamamına). Yol yasak bölge köşelerinin yakınından geçince titreme.
   - Bozuk çerçeve bu oturumda da: PC'de 3, kartta `framing 1` (açılışta).
   - **Açık (karar Esra'nın):** sıcaklık 0 + sabit seed'de tekrarlar birebir aynı cevap verdi; K-015'teki
     senaryo başına 20 tekrar bu ayarla anlamsız. Faz 5 için sıcaklık > 0 ya da farklı seed gerekli.
   - Araç tanımları şimdilik betikte taslak; 4.3'te `llm_agent`'a taşınacak, betik oradan okuyacak.
2. **4.1 Kart, kalan kurallar** (her biri ayrı adım, kartta sınanır): `LIMIT` (görevde ret, hızda
   kırpma) · `WAIT_CMD`/`SPEED_LIMIT_CMD`/`STOP_CMD` · `FRESHNESS` (zaman eşitlemesi, protocol §6) ·
   araç konumunun coğrafi sınırı + `RECOVERY` + ret sayacı (RULES §5) · K-042 kart tarafı (`HALT(0)`) ·
   `CONSISTENCY` en sonda (takvim kayarsa ilk kısılacak, plan §7).
3. **4.2 Köprü:** K-042 köprü tarafı (Nav2 hedefini iptal), yeni görev komutlarının çevirisi,
   ret gerekçesi ajanın konusuna.
4. **4.3 Ajan (`llm_agent`):** araçlar `git`, `bekle`, `hiz_siniri`, `dur`; yer isimleri
   `ika_saha.yaml`'dan (K-044); gerekçe ajana geri verilir, görev başına en çok 3 deneme (RULES §5.4).
5. **4.4 Uçtan uca (Esra'yla)** → `v0.4.0`.

---

**2026-10-08:** `oto/faz3` (deneme 3, 3.2c yüklemesiz, 3.3 kart tarafı `guard_velocity`)
incelendi ve `main`'e birleştirildi (fast-forward, push edilmedi). Karta hiçbir şey yüklenmedi.

**Faz 3'ün son adımları:**
1. ~~İKA tavanını bul (K-039)~~ **bitti (2026-10-08):** RULES §1 yeniden kuruldu (bekçi
   0,6 m/s · 0,6 rad/s; tavan 3,6 m/s, KTR'den). Açık kalan: bekçinin doğrusal ivmesi,
   Faz 4'ten önce Nav2'nin `/cmd_vel` kaydından ölçülecek.
2. ~~Karta yükleme~~ **bitti (2026-10-08):** `main` (`bb64cd9`) Debug, text 39 724 B, 0 uyarı;
   yazıldı ve doğrulandı. `decision_test` ve `link_test` kartta hepsi geçti. `decision_test`'e
   hız komutu eklendi: NORMAL'de `VELOCITY_CMD (300, 100)` → araca `DRIVE (300, 100)`,
   `VERDICT` yok; HOLD'da araca yalnız sıfır hız (10 `DRIVE`, hepsi 0).
3. **3.3 köprü (K-040), adım 1 bitti (2026-10-08):** `Link` ve `Heartbeat`
   `shared/protocol/python/ika_protocol/link.py`'de; testler oradan alıyor. Yeni: `strict=False`
   bozuk çerçeveyi `rx_errors`'a sayıp geçer (köprü için). Kartta `decision_test` 7/7,
   `link_test` 9/10: biri PC tarafında `framing` (COBS) hatasıyla kaldı, tekrarlanmadı.
   Bir kez daha `Link` açılışında görüldü (ajan kanalı). 70 açılışta tekrarlanmadı.
   **Tahmin ve düzeltme (kanıtlanmadı):** `Link` oturum kimliğini öğrenmeden atladığı
   (doğrulanmamış) çerçeveyle de "temiz" sayıyordu; USB'de bekleyen eski baytların ardından
   gelen bozukluk hata sayılıyordu. Artık yalnız imzası doğrulanmış çerçeve sayılıyor.
   Sonra `link_test` 5/5, `decision_test` 3/3. **Açık:** tekrar görülürse tahmin yanlış.
   **Adım 2 bitti:** `guard_bridge/convert.py` + 25 test (kasıtlı 4 hatanın 4'ü yakalandı).
   **Adım 3 bitti:** `vehicle_bridge.py`, kartla simülasyonsuz: HOLD sıfır hızı `/cmd_vel`'e
   20,1 Hz; sabit `map → base_link` → TELEMETRY, kartta yaş ≤ 44 ms; tek `DRIVE (0,3)`'ten
   0,5 s sonra bekçi köpeği sıfırladı (Gazebo DiffDrive son hızı süresiz uygular); 1200 DRIVE'da
   0 bozuk çerçeve. Denenmedi: GOAL → Nav2 (adım 6).
   **Adım 4 bitti:** `agent_bridge.py` (+ `/guard/reset` servisi; `Link.adopt_hello`,
   `Link.wire_seq`). Kartla simülasyonsuz, iki köprü birlikte: reset → NORMAL; izinli hedef
   ACCEPTED ve GOAL araç köprüsüne ulaştı; kazı → GEOFENCE / GOAL_IN_FORBIDDEN, ipucu (8, 2) m
   `/guard/verdict`'te; `odom` çerçeveli hedef gönderilmedi; `/cmd_vel_nav` 0,25 → `/cmd_vel`
   0,25; ajan köprüsü durunca kart HOLD, `/cmd_vel`'e 20 Hz sıfır.
   **Adım 5 bitti:** `navigation.launch.py`'de `TO_GUARD` (bt_navigator `goal_pose` →
   `/goal_pose_unused`; controller ve behavior `cmd_vel` → `/cmd_vel_nav`), `bridge.launch.py`.
   Doğrulandı: `/cmd_vel`'e yazan tek düğüm `vehicle_bridge`; `/goal_pose`'u yalnız köprü dinliyor.
   **Adım 6 bitti (Esra'yla, 2026-10-08), Faz 3.3 BİTTİ:**
   - RViz hedefi → kart → CAN → Nav2: izinli hedefler ACCEPTED ve `GOAL` sayacı yalnız onlarda arttı.
   - Kazı/personel hedefi (6,22, −6,97) → REJECTED · GEOFENCE · GOAL_IN_FORBIDDEN, ipucu (8, 2) m;
     Nav2'ye ulaşmadı, yeni hareket başlamadı (deneme 3'te Nav2 tek başına 0,4 m oynatmıştı).
   - Her hız komutu karttan geçti: 10 s'de `VELOCITY_CMD` +82 = `DRIVE` +82; PC'de bozuk çerçeve 0.
   - ST-LINK kablosu çekildi (kart ST-LINK'ten beslendiği için kapandı): bekçi köpeği 0,5 s'de
     durdurdu, Nav2 karta uğramadan aracı oynatamadı ("Failed to make progress").
   - **Yeniden bağlanma eklendi** (`link.open_link`, `LINK_LOST`, `Heartbeat` port kaybında
     durur; iki köprü saniyede bir dener, kopukken komutları atar). Denendi: koptu → 0,5 s'de
     araç durdu → kart yeniden başladı → ~1 s'de iki köprü yeni oturuma bağlandı, kart HOLD;
     HOLD'da Nav2'nin hızları araca sıfır olarak gitti; reset → NORMAL, `VELOCITY_CMD` +705 =
     `DRIVE` +705, araç hedefi tamamladı.
   **Açık sorunlar (adım 6'da görüldü):**
   - ~~Yerel costmap lidarsız da dondu~~ **YANLIŞ TEŞHİS (düzeltildi aynı gün):** `/local_costmap/costmap`
     8 s'de 0 mesajdı, ama yerel costmap'te `always_send_full_costmap: false`: tam harita yalnız
     boyut/orijin değişince gider, gerisi `/local_costmap/costmap_updates`'e (1,67 Hz, canlı).
     Okunan "99" değerleri bekleyen eski tam haritadandı. Ders: bir konunun susması donma değildir,
     önce yayın biçimine bak. "Collision ahead" büyük olasılıkla AMCL kaybından (aşağıda). K-038 geçerli.
     **(2026-10-14: bu tahmin yanlış çıktı, yukarıda 4.0'a bakın.)**
   - **AMCL ~14 m kayboldu, araç personel yasak bölgesine girdi → nedeni bulundu, önlendi (K-041):**
     Gazebo (3,52, −5,95), AMCL (12,64, 5,29). Zincir ölçüldü (`tools/amcl_push_bench.py`):
     araç konteynere dayanınca odometri 60 s'de 15 m "ilerledi", AMCL 5,7–14,1 m koptu ve
     toparlanmadı. Dönüşte odometri ayrıca %16 fazla sayıyor (360° komut: gerçek 200°, odom 232°,
     AMCL 209°); düz gidişte doğru. AMCL ayarı çözmedi (`alpha3` 0,8: 5,5 m; `recovery_alpha`:
     5,6–5,8 m). **collision_monitor (approach)** eklendi: araç konteynere 0,36–0,58 m kala duruyor,
     AMCL hatası ≤ 0,17 m; normal gezinme (kapı önü, konteyner arkası dar yol) etkilenmedi.
     Tez için bilinen sınır: kartın konuma dayanan kuralları konum kaynağı kadar güvenilir.
     Yan bulgu: komutu araç tam uygulamıyor (0,5 rad/s → gerçek 0,28; 2 m → 1,24 m).
   - **Kart kabul eder, Nav2 ulaşamaz şeridi (~0,9 m):** (27,27, −1,34) kartın izinli alanında
     (pay sonrası x ≤ 27,6), ama Nav2'de maliyet 99 (iç yarıçap 0,875 şişirmesi, merkez x ≲ 26,7).
     Planlayıcı "tolerance 0.00" ile vazgeçti. Katmanlar farklı soru soruyor (yasak mı / sığar mı).
   - **Çalışırken bozuk çerçeve:** bir oturumda ~58 000 çerçevede iki kanalda da 2'şer; köprü sayıp
     geçti. Açılış düzeltmesi (`fbc20d1`) bunu açıklamıyor: seyrek akış içi bozulma da var.
   - **Reset'ten sonra Nav2 eski hedefe devam etti** (yeni hedef verilmeden). **Karar verildi
     (K-042):** HOLD'a geçişte kart `HALT(0)` gönderir, köprü Nav2 hedefini iptal eder (bağlantı
     kopunca ve kart yeniden başlayınca da). Uygulama Faz 4'te, RULES §5 o zaman güncellenir.
   - Kart E5V'den beslenmediği için uçtan uca "kart açık, yalnız kalp atışı kesildi" denenmedi
     (`decision_test` bunu sınıyor: 523 ms). `tools/unplug_test.py` başlığında E5V kurulumu var.
   Önceki plan: Nav2 konularının yeniden adlandırılması, `Link`'in
   `ika_protocol/link.py`'ye taşınması, `agent_bridge` ve `vehicle_bridge`. Doğrulama: PC'de
   `Link` ve çeviri birim testleri; uçtan uca (RViz hedefi karttan geçiyor, dışarıdaki hedef
   reddediliyor, kablo çekilince araç duruyor) kartla, Esra'yla.

**Deneme 3 bulgusu (tez için):** yasak bölgelere ve kapı dışına 4 hedef, Nav2 dördünü de
reddetti, ama ret sırasında kurtarma hareketleri aracı 0,4 m'ye kadar oynattı; kartın reddi
`GOAL` göndermediği için araç kıpırdamaz.


**Araç değişiyor: TurtleBot 4 → ORINIUM İKA modeli** (K-034, 2026-10-06). Deneme
scratchpad'de yapıldı; model depoya alındı (adım a), henüz başlatma dosyasına bağlı değil. Bulgular:
- **Port üç mekanik değişiklik:** `<sdf version>` 1.11 → 1.9 (Fortress'in sdformat12'si en
  çok 1.9 okur; model doğrulamadan geçti), mesh yolları `file:///home/esra/ugv_telemetry_new/...`
  (artık yok) → `model://ika_arac/meshes/...`, eklentiler `gz-sim-*-system` / `gz::sim::` →
  `ignition-gazebo-*-system` / `ignition::gazebo::`. `<gz_frame_id>` değişmedi: Fortress'in
  ignition-sensors 6.9'u onu da tanıyor (kütüphanedeki dizgilerden doğrulandı).
- **Dünyaya eklenecek sistemler:** Sensors (`<render_engine>ogre2`), Imu, Contact. Model
  bunları getirmiyor (TurtleBot 4 getiriyordu).
- **Boş dünyada doğrulandı:** lidar `/scan` 720 örnek, çerçeve `lidar_link`, kendi gövdesini
  görmüyor (en yakın 2,50 m = kutu); `/camera/image` 640×480 RGB, `/camera/depth_image`
  640×480 metre; kule kamerası çalışıyor; düz sürüş 0,5 m/s geri: gerçek 2,440 m, odom 2,441 m.
- **Dönüşte odometri %14 fazla:** gerçek 123°, odom 140°, ~10 cm kayma. 12 tekerlek dönerken
  kayıyor (paletli araç gibi); DiffDrive kaymayı bilmiyor. RTAB-Map'in düzelteceği hata.
- **Hız:** `ika_saha` kopyasında İKA ile %100 (2 × 20 s, kule kamerası açık; tavan, çünkü
  `real_time_factor` 1,0). TurtleBot 4 ile %46: yavaşlık sahneden değil TurtleBot 4'ten
  (hangi parçası, ölçülmedi). İKA ölçümünde ROS köprüleri yoktu.
- **Orijinal modelde:** `FRF` tekerleğinin görseli `BRF.STL`'i kullanıyor (tekerlekler aynı,
  görünüşte fark yok). ORINIUM'un parkur dünyası `<dart><collision_detector>bullet` kullanıyor
  ("dartsim varsayılanıyla RTF ~%7, bullet 4× hızlı" notu); bizde %100 çıktı, gerekmedi.
- **Saha dar:** araç 1,15 m geniş; güney koridoru 1,5 m, kamyonet-konteyner 1,4 m, kazı
  alanının kuzeyi 0,38 m. Geçitler ~3 m'ye çıkmalı.

Deneme dosyaları (scratchpad, oturumla silinir; depoya alınırken yeniden üretilecek):
`ika_deneme/models/ika_arac/` (çevrilmiş model + 21 STL), `ika_deneme.sdf` (boş dünya),
`saha_ika_arac*.sdf` (`ika_saha` kopyası + İKA).

**Faz 3: deney sahası `ika_saha` yazılıyor** (K-032). Hazır TurtleBot 4 dünyaları yerine
sıfırdan, blok blok, Esra'nın onayıyla yazılan bir açık saha. Çalıştırmak için (depo
kökünden, önceki simülasyon kapalıyken):

```bash
ros2 launch ros2_ws/src/ika_sim/launch/ika_sim.launch.py
python3 ros2_ws/src/ika_sim/tools/gen_textures.py   # dokular değişecekse; çıktı aynı kalır
```

Dosyalar (`ros2_ws/src/ika_sim/`; İKA ile, K-034):
- `models/ika_arac/`: İKA modeli (Fortress'e çevrilmiş, 21 STL). Başındaki yorum kaynağı ve 4 değişikliği anlatır.
- `config/bridge.yaml`: ROS ↔ Gazebo köprüsünün 9 konusu.
- `worlds/ika_saha.sdf`: dünya. Başındaki yorum blokların sırasını ve Fuel model kuralını anlatır.
- `launch/ika_sim.launch.py`: Gazebo (`ros_gz_sim`, Fortress) + köprü (`config/bridge.yaml`) +
  4 sabit `tf`. Arama yoluna `worlds/` ve `models/`'i ekler. Araç dünyanın içinde (`<include>`).
- `tools/gen_textures.py` → `worlds/textures/`: `asfalt.jpg` (1650×1050, 33 × 21 m, 2 cm/px; K-035'te büyüdü, yoğunluklar korundu),
  `konteyner.jpg`, `yasak.jpg`, `cop.jpg`. Sabit tohum; yeni doku listenin sonuna eklenir ki
  eskilerin rastgele dizisi değişmesin (denetlendi: bayt bayt aynı).

Bloklar:

| Blok | İçerik | Durum |
|---|---|---|
| 1 | Fizik (3 ms), 3 dünya eklentisi, sahne, güneş ışığı, 60 × 40 m zemin | ✅ simde görüldü; kamera, lidar, `/odom`, `/clock` veri veriyor |
| 2 | `<sky>`, 25 Jersey Barrier (kuzey/güney 8'er, merkezler 4 m arayla; batı 5; doğu 4), doğuda kapı | ✅ simde görüldü (K-035'teki 32 × 20 m hâli de, 2026-10-06) |
| 3 | Doku üreteci, saha yüzeyi (yalnız `visual`, zeminden 2 mm yukarıda, `albedo_map`) | ✅ simde görüldü: çatlaklar, lekeler, zemin numaraları |
| 4 | Konteyner (kendi kutumuz, 6,06 × 2,44 × 2,59 m, merkez (8, 4,5)), kamyonet (Fuel Pickup, (20,3, 4,5)), çöp konteyneri (kendi kutumuz, 1,4 × 2,0 × 1,3 m, (−1,5, 7)); K-035 yerleri | ✅ düzeltilmiş hâli simde görüldü (2026-10-06) |
| 5 | Yasak bölgeler: 3 zemin boyası (`yasak.jpg`, yalnız `visual`, z = 0,004), kazı alanı köşelerine 4 koni (Fuel Construction Cone, `<static>` include'da eklendi), personel alanına 2 masa (Fuel Table), yakıt alanına 2 tank (kendi silindirimiz) | ✅ simde görüldü (2026-10-06); hıza etkisi ~1 puan (aşağıda) |

Blok 4'ün ilk hâlinde iki sorun çıktı, düzeltildi ve simde doğrulandı:
- Kamyonet konteynere 18 cm giriyordu. Kamyonet modeli inç biriminde, 5,66 m ve simetrik
  değil (DAE'den ölçüldü). Konteyner x 8 → 6, kamyonet 13,8 → 13,4: arada 1,4 m, kamyonetle
  bariyer arasında 0,5 m.
- Fuel'deki Dumpster simsiyah göründü ve simülasyon hızı **%0,67**'ye düştü (10 s'de
  simülasyon saati ilerlemedi, Gazebo sunucusu bir çekirdeği doldurdu). Model statik değil,
  çarpışma şekli mesh, malzemesi eski tür. Yerine kendi statik kutumuz (`cop.jpg`).
- Doğrulandı (2026-10-06): hız oranı **%36–38** (öncekinden biraz yüksek), kamyonet ile
  konteyner arasında boşluk görülüyor, çöp konteyneri yeşil ve "ATIK" yazısı okunuyor.
- Bilinen, düzeltilmeyecek: konteynerin üst yüzünde doku uzuyor (kutunun 6 yüzüne aynı
  resim). Robotun kamerası ~0,3 m yüksekte, üst yüzü görmez; sonuç tablosuna satır eklemez.

Blok 5'te ekrandaki hız %24 göründü. Ölçüldü, düşüş çıkmadı (kontrol deneyi: aynı
çalışan simden Blok 5'in 11 modeli `/world/ika_saha/remove` servisiyle silindi, tek değişken):

| Durum | 20 s ölçüm 1 | 20 s ölçüm 2 | Ortalama |
|---|---|---|---|
| Blok 5 var | %46,9 | %45,9 | **%46,4** |
| Blok 5 yok | %47,2 | %47,5 | **%47,4** |

Fark iki ölçümün kendi arasındaki oynamayla aynı boyda. (Bu ölçümler 20 × 12 m sahada;
32 × 20 m sahada TurtleBot 4 ile %42,7 ve %45,4.)

Yerleşim (K-035, 32 × 20 m; 1 karakter ≈ 1 m yatay, 1 satır = 1,5 m dikey):

```
     x: −3                              29
y 10   ┌─────────────────────────────────┐
       │ DD                              │
       │ DD     KKKKKKK     PPPPPPP      │
       │        KKKKKKK     PPPPPPP      │
       │                                 │
       │                XXXX              
y  0   │   S            XXXX              ← kapı (y −1,97…1,97)
       │                XXXX              
       │                                 │
       │      MMMMMMM       YYYYYYY      │
       │      MMMMMMM       YYYYYYY      │
y −10  └─────────────────────────────────┘
 S başlangıç (0,0)  D çöp  K konteyner  P kamyonet
 X kazı  M personel (masalar)  Y yakıt (tanklar)
```

- İzinli alan: bariyerlerin içi. Bariyerin tabanı 0,81 m geniş (çizgiden 0,405 m içeri
  taşar); izinli çokgenin bariyer çizgisinden ne kadar içeride olacağı 3.2'de İKA'nın
  boyutuna (1,78 × 1,15 m) göre belirlenecek.
- Yasak 1, personel alanı: x 3…9, y −8,2…−4,5. Yasak 2, kazı alanı: x 13…16, y −1,5…1,5.
  Yasak 3, yakıt alanı: x 17…23, y −8,2…−4,5.
- Geçitler: konteyner arkası 3,9 m, kamyonet arkası 4,1 m, güney koridoru (kazı ile yasak
  bölgeler arası, y −4,5…−1,5) 3,0 m, konteyner–kamyonet 6,3 m. Kazı alanı düz yolu keser;
  kuzeyinden ya da güney koridorundan dolanılır.
- Yer adı / güvenli nokta adayları: başlangıç (0, 0), kapı önü (~26, 0), konteyner
  arkası (~8, 7,6), konteyner önü (~8, 2), kuzeybatı (~1, 6).

**3.2b'de öğrenilenler (Nav2, 2026-10-07):** sıra, deneme 2 geçene kadar yapılanlar.
1. **Nav2'nin açılışında servis cevabı kaybolabilir.** `lifecycle_manager_navigation` planlayıcıyı
   yapılandırdı ama cevabı alamadı (`failed to send response ... timeout`), gezinme düğümleri
   açılmadı. Yeniden başlatınca düzeldi; bir daha görülmedi.
2. **Nav2 "Goal succeeded" diyebilir ve araç kıpırdamaz.** Controller hedefi `map`'ten `odom`'a
   çeviremeyince (tf bayat) hedef (0, 0)'da kalıyor, araç da (0, 0)'da olduğu için "vardım"
   diyor (`nav_2d_utils::transformPose`'un dönüş değeri yok sayılıyor). Konum hatası varken
   başarı mesajına güvenilmemeli.
3. **Costmap'lerin tf tamponu donuyordu; sebep lidar katmanı (ölçüldü).** Belirti: controller'ın
   `map → odom`'u (sonra bütün tf'si) bir anda bayatlıyor, süreç Ctrl+C'ye cevap vermiyor.
   - İlk hipotez FastDDS idi; CycloneDDS'e geçildi (`~/.bashrc`: `RMW_IMPLEMENTATION`), sorun
     sürdü: **hipotez yanlıştı**. Ölçmeden sistem değişikliği önerildi; ders: önce tetikleyiciyi bul.
   - AMCL yayın yapıyordu (9 Hz), ayrı bir dinleyici 250 s hiç donmadı: sorun controller'a özgü.
   - RViz kapalıyken 130 s donma yok, RViz açılınca ~50 s sonra donma: tetikleyici yük.
   - Komut satırından costmap aboneliğiyle aynı yük: lidar katmanı olan local costmap ~75–130 s'de
     dondu, lidar katmanı çıkarılan global costmap 4 dk donmadı (Deney A). İki costmap'te de
     lidar katmanı yokken aynı yük altında 4 dk donma yok, düğümler normal kapanıyor.
   - Mekanizma kanıtlanmadı (tf2 `MessageFilter` kilitlenmesi şüphesi; `gdb` `sudo` istiyor).
   - Sonuç: iki costmap'te de lidar katmanı yok, yakın çevre statik haritadan. Bedeli: haritada
     olmayan yeni engel görülmez.
4. **Keepout filtresi şişirmeden SONRA uygulanıyor.** Planlayıcı yasak bölgelerin dibinden
   (1 m'lik güney koridoru) plan yaptı, controller gövdenin taşacağını görüp durdu. Keepout maskesi
   şişirmeden önce okunan bir `StaticLayer` yapıldı; `costmap_filter_info_server` kalktı.
5. **Konum bulucuyu araç başka yerdeyken yeniden başlatmak.** Nav2 yeniden açılınca AMCL aracı
   (0, 0)'da sanıyor. Düzeltme: `/initialpose` (RViz'de "2D Pose Estimate"). Yasak payının içinde
   kalan araç her yönde "çarpışma" görüp kurtulamadı; simde `/world/ika_saha/set_pose` ile
   başlangıca alındı.
6. **Konteyner ile kazı arasında 1,24 m'lik darboğaz** (konteyner köşesi (11,03, 3,28), kazının
   paylı köşesi (12, 2,5)). Araç 1,15 m: planlayıcı geçilebilir saydı, harita ~0,5 m kaymış ve
   lidar katmanı yok, araç gerçek konteynere sürtündü. İze 0,3 m pay (`footprint_padding`).
   K-035'te "kazı kuzeyden dolanılır" derken bu darboğaz hesaplanmamıştı.
7. **`use_maximum` Humble'da costmap düzeyinde.** Katmana yazılınca yok sayıldı ve keepout katmanı
   haritayı ezdi: konteyner costmap'ten silinmişti. Ayarın düğümde tanımlı olduğu
   `ros2 param list` ile denetlenmeli; kütüphanede adın geçmesi yetmez.
8. **Şişirme yarıçapı iç yarıçaptan büyük olmalı.** Pay iç yarıçapı 0,875 m'ye çıkardı, şişirme
   0,8'de kalınca kademeli şerit kayboldu. 1,5 m.
- RViz: Map ekranlarında Durability "Transient Local" olmalı (Nav2 haritaları bir kez yayınlar).
- Her ayar değişikliğinden sonra hedef vermeden önce costmap ölçülmeli (konteyner var mı,
  darboğaz kapalı mı): `/global_costmap/costmap`'ten hücre değerleri.

**Deney sahasında öğrenilenler:**
- **Şarj istasyonu robotun 0,157 m önünde.** TurtleBot 4 istasyonu robotun önüne, ona dönük
  koyar (`turtlebot4_spawn.launch.py`, `/sim_ground_truth_dock_pose` x = 0,157). Robot
  istasyondan geri geri, batıya çıkar. Batı bariyeri bu yüzden x −2 → −3'e alındı.
- **3B görünüm `<scene><background>`'ı kullanmıyor**, gökyüzü siyah kaldı. `<sky>` çözdü.
- **Göreli doku yolu `.sdf`'nin klasörüne göre çözülüyor** (`textures/asfalt.jpg` çalıştı).
- **`ign sdf -k` Fuel adreslerini çözemez** ("callback is empty", her include için 2 hata).
  Yapı hatası ayrı sayılır: Fuel dışındaki hata sayısı 0 olmalı. Modeller önbelleğe
  `ign fuel download -u <adres>` ile indirilir.
- **Modeli ölçmeden yerleştirme.** Kamyonetin boyu tahminden 0,66 m uzun çıktı. Mesh'in
  sınırları DAE'deki köşe listesinden ve `<unit meter>`'dan hesaplanabilir.
- **HMI'daki pil %0 yanıltıcı:** `/battery_state` `percentage: 1.0` (0–1 arası, yani %100).
- **Ekrandaki hız yüzdesi ölçüm değil.** Anlık değer saniyeler içinde %28–%65 arası oynuyor
  (bir kez %0 → %119: sim takılıp açığı kapattı). Ölçüm: `/world/ika_saha/stats`'ı 20 s
  kaydet, `sim_time` ve `real_time`'ın ilerlemesini böl. Ölçerken GUI'de kamera oynatılmaz
  (ekranı çizmek de aynı iGPU'yu kullanıyor). Önceki "%30" ve "%36–38" ekrandan okunmuştu.
- **Modeli dosyaya dokunmadan simden çıkarmak:** `ign service -s /world/ika_saha/remove
  --reqtype ignition.msgs.Entity --reptype ignition.msgs.Boolean --req 'name: "<ad>" type: MODEL'`.
  Sim yeniden açılınca geri gelir. Kontrol deneyi için uygun.
- **Odometri patinajı göremez.** İKA kuzey bariyerine dayanmışken klavyeyle ileri sürüldü:
  gerçek (4,3, 9,0) / 90°, odometri (33,6, 21,4) / ~35° (29 m, 55° sapma). Tekerlekler
  yerinde döndü, DiffDrive her turu ilerleme saydı. RViz `odom` çerçevesinde bunu gösterir;
  3.1'de RTAB-Map'in `map → odom` düzeltmesi bu hatayı kapatmalı.
- **Kamera görüntüsü optik çerçeveyle etiketlenmeli** (z ileri, x sağa, y aşağı). Araç
  çerçevesiyle etiketlenirse derinlik yanlış yöne çevrilir. Modelde `<gz_frame_id>`
  `camera_optical_frame`, `camera_link`'ten dönüşü (−90°, 0, −90°) başlatma dosyasında.
- **RViz'de `use_sim_time:=true`:** mesaj damgaları sim saatinde; RViz duvar saatiyle
  çalışırsa mesajları eski sayabilir. Doğrulama: Time panelinde ROS Time küçük bir sayı.
- **Kendi ayrıştırma betiğine güvenme.** İKA'nın odometrisi dönüşte "0°" çıktı: awk `pose`
  bloğundan sonra `twist`'teki `z: 0`'ı da okuyordu. Doğru bloktan okununca 140°.
- **Test sürüşünde engele olan uzaklığı önce hesapla.** İlk İKA sürüşü 3,9 m gitmeye
  çalıştı, burnu 3,5 m'deki kutuya dayandı; odometri dönen tekerlekleri saymaya devam etti
  (gerçek 2,71 m, odom 4,44 m). O sürüş karşılaştırmada kullanılmadı.
- **Simülasyon gerçek zamanın ~%46'sı hızında** (ölçüldü, 2026-10-06; Intel iGPU, NVIDIA sürücüsü yok). Harita ve
  Nav2 `/clock`'u kullandığı için etkilenmez, yalnızca uzun sürer. Kart ise gerçek zamanda
  çalışır (kalp atışı 500 ms): 3.3'te köprü tasarlanırken hesaba katılmalı.

**Kablo çekme testi yapıldı** (K-029, `tools/unplug_test.py`). Kart E5V'den beslendi (JP5 [5-6],
CP2102 +5V → CN7 pin 6), ajanın USB kablosu (CN1) test sırasında elle çekildi. Üç
çalıştırmada kopma bölümü eksiksiz geçti:
- Son kalp atışından ilk sıfır hıza **500–501 ms** (kartın saatiyle: son `HEARTBEAT_ACK`'in
  `ts_ms`'i → ilk `DRIVE`'ın `ts_ms`'i). Bilgisayarın saatiyle 569–605 ms: fark iki USB
  köprüsünün gecikmesi.
- Araç kanalına 20 Hz sıfır hız (41–42 `DRIVE`, aralık 48–52 ms), kart `HOLD`'da, araç
  kanalında aynı oturum, kartın saati ilerliyor: kopma kartı yeniden başlatmıyor.
- **Bulgu: kablo geri takılınca kart yeniden başlıyor** (3/3; yeni oturum, ajan portu Linux'ta
  görünmeden 61 ms önce). JP3 çıkarılınca da oluyor. `RCC_CSR` temizlenip CN1 yeniden
  takıldı: yalnızca `PINRSTF` (`0x04000010`). Besleme düşmüyor, yazılım reseti değil. JP3'süz
  birikmiş bayraklarda `SFTRSTF` vardı: ST-LINK açılırken işlemciyi resetliyor, JP3
  yalnızca yolunu değiştiriyor gibi. Kart `HOLD`'da açılıyor (güvenli taraf). Bu yüzden geri
  takma sonrası hata sayaçları ve `HOLD` mandalı fiziksel testte ölçülemedi.
- Test sonrası JP5 5V_STLK'e dönecek, E5V teli çıkarılacak (Esra, "Sırada"). JP3 takılı.

**Kablo çekme testinde öğrenilenler:**
- **Kanal başına "kuruldu" bayrağı var.** Kart bir kanala, o kanaldan imzalı çerçeve gelene
  kadar 500 ms'de bir `HELLO` yayınlıyor (`channel.c`). İlk betik araç kanalındaki her `HELLO`'yu
  "kart yeniden başladı" sandı. Yeniden başlamanın işareti `HELLO` değil, oturum kimliğinin
  değişmesi. Betik artık başta araç kanalından telemetri de gönderiyor.
- **Kart yeni açılınca ilk telemetri çerçevesi kayboldu** (`frames_ok 0 → 0`, bir önceki
  çalıştırmada `1 → 1`). Tahmin: CP2102 kartla aynı anda enerjilenirken hatta bir çöp bayt
  kalıyor ve ilk çerçeveyi bozuyor. Doğrulanmadı. Köprü için ders: ilk çerçeveden önce bir
  ayraç (`0x00`) göndermek.
- **Tahmin edilen sebep yanlış çıkabilir.** Reset için JP3'ten şüphelenildi, JP3'süz deney
  bunu eledi. Önce kontrol deneyi (JP3 takılıyken anı ölçmek), sonra tek değişken.
- **İşlemci reset sebebini kendisi tutuyor** (`RCC_CSR`, `0x40021094`: bit 26 `PINRSTF`,
  27 `BORRSTF`, 28 `SFTRSTF`). Bayraklar birikiyor; anlamlı olması için önce `RMVF` (bit 23)
  ile temizlenmeli. Yazılım reseti `PINRSTF`'i de kaldırır.
- **Araç "Error" dese de yazma olmuş olabilir.** `STM32_Programmer_CLI -w32` yazdıktan sonra
  geri okuyup karşılaştırıyor; `RMVF` kendiliğinden 0'a döndüğü için "Failed to download
  data" dedi, bayraklar yine de temizlenmişti. Sonuç her zaman ayrı bir okumayla denetlenmeli.
- **Bilgisayarın saati bu ölçüm için yanlış araç.** Kablo çekilirken yazma bir süre işletim
  sisteminin tamponuna "başarılı" gidebiliyor, gelen çerçeve de USB köprüsünde bekliyor.

**Faz 2.6 kapandı** (K-025, K-026). Plandaki "bitti sayılır" ölçütleri kartta, `tools/decision_test.py`
ile (26 denetim, Debug ve Release'te, art arda çalıştırmalarda hepsi geçti):
- **İzinli hedef geçiyor:** `GOTO_CMD` (100, −200) → `VERDICT ACCEPTED`, `GOAL` FDCAN1 → CAN
  hattı → FDCAN2 → araç kanalından aynı değerlerle çıktı.
- **Dışarıdaki hedef gerekçeyle dönüyor:** izinli alanın dışı, yasak bölge, izinli alanın tam
  kenarı → `GEOFENCE` + doğru gerekçe + en yakın güvenli nokta. Araca hiçbir `GOAL` gitmedi.
- **Kalp atışı:** kesilince 523–525 ms sonra araç kanalına 20 Hz sıfır hız başladı (50 ms
  aralık, kartın zaman damgasından), kart `HOLD`'a geçti ve kalp atışı geri gelince
  `SIFIRLA` olmadan `NORMAL`'e dönmedi. Fiziksel kablo çekme testi sonradan yapıldı (yukarıda,
  K-029).
- **Karar süresi** (`goto_timing`, GOTO_CMD çerçevesinin son baytından `VERDICT` ve CAN
  mesajı kuyruğa girene kadar, HMAC dahil): **Release 169–177 µs** (12 karar), Debug
  853–886 µs (24 karar). PA8 pini aynı aralıkta 1 oluyor; mantık analizörü olmadığı için
  pin ölçülmedi (K-009).
- Yeni modüller: `guard/` (denetim sırası ve durum makinesi), `site/` (deneme harita
  verisi), `rules/heartbeat/` (TIM6), `vehicle_node/` (FDCAN2, araç tarafı),
  `timing/timing` (pin). CubeMX'te TIM6 ve PA8, komut satırından (K-026). Protokole
  `NO_HEARTBEAT` gerekçesi eklendi, şema özeti `0xD9092C66` (`f7d9822`).
- PC testleri: 210 (`python3 -m pytest shared/protocol/tests firmware/tests`; 3.2a'dan sonra
  `shared/site/tests` ile 229). `guard`'a
  kasıtlı hata konmuş 14 kopyanın 14'ü yakalandı.
- **Kartta şu an Release derlemesi yüklü.**

**Faz 2.6 c ve d'de öğrenilenler:**
- **Bilgisayarın okuma anı ölçüm değildir.** "1 saniyede kaç `DRIVE`" sayımı 26 çıktı: önceki
  adımda biriken çerçeveler de sayılmıştı. Kartın her çerçeveye koyduğu `ts_ms` ile aralık
  ölçülünce 50 ms çıktı.
- **Elle hesaplanan beklenen değer de yanılabilir.** İki test, en yakın güvenli noktayı yanlış
  hesapladığım için kaldı; kod doğruydu. Kare uzaklıklar yazılı hesaplanıp testin yanına not
  edildi.
- **Arka planda gönderen bir iş parçacığı sayaç sırasını bozabilir.** Kalp atışı ayrı
  iş parçacığından giderken komutun sayacı `agent.seq`'ten okunuyordu, arada ilerleyebilirdi.
  Sayaç gönderilen baytlardan okunuyor, sayaç verme ile yazma aynı kilitte.
- **Kart yeniden başlarken çerçeve yarıda kalır.** USB köprüsü yarım baytları tutup port
  açılınca veriyor. İlk geçerli çerçeveden önceki bozukluk atlanıyor (köprü için §10).
- **`-Werror` bazı kasıtlı hataları derletmez** (`uint8_t ≤ 255` her zaman doğru). Hatalı
  kopya derlenebilir yazıldı, yakalandı. Faz 2.6 a'daki dersin tekrarı.
- **CubeMX komut satırından çalışıyor** (`-q`, `config load` + `project generate`). Değişiklik
  önce projenin geçici bir kopyasında üretilip farkı incelendi (K-026).

**Faz 2.6 b bitti: coğrafi sınır** (`firmware/app/rules/geofence/`, K-024).
`geofence_check(fence, nokta)` → `OK` / `OUTSIDE_ALLOWED` / `IN_FORBIDDEN`. Işın atma,
yarı açık kural, tamsayı ve 64 bit çarpım. Sınırın üstü her zaman ihlal. Kod henüz
kimseye bağlı değil (c'de `GOTO_CMD`'ye bağlanacak), kartta süre ölçülmedi. Testler PC'de:
`firmware/tests/test_geofence.py`, 45 test. 24 elle hesaplanmış durum, delik, uç
koordinatlar, geçersiz sınırlar ve dolanma sayısı kullanan bağımsız bir Python referansına
karşı 51 462 rastgele nokta (11 236'sı tam sınırın üstünde). Kasıtlı hata konmuş 13
kopyanın 13'ü yakalandı.

**Faz 2.6 b'de öğrenilenler:**
- **Yakalanmayan her "hata" hata değildir.** İlk denemede 10 kopyanın 4'ü yakalanmadı. Üçü
  aynı davranışın başka bir yazımıydı: yarı açık kuralın öbür yönü (iki tarafta da `>=`),
  ulaşılamayan bir dal (`> 0` yerine `>= 0`, çünkü o durumda kod zaten "sınırda" deyip
  çıkmış oluyor), ışını sola atmak. Asıl hata iki tarafın farklı kural kullanmasıydı, o da
  yakalandı.
- **Dizinin dışını okumak cevabı değiştirmeyebilir.** Yasak çokgen sayısı denetlenmeyince kod
  4 elemanlı dizinin 5.'sini okudu. Arkadaki bellek tesadüfen sıfırdı, sonuç doğru çıktı.
  Test derlemesine `-fsanitize=address,undefined` eklenince yakalandı.
- **Denetim aracı yapının içindeki taşmayı göremez.** İzinli çokgenin 17. köşesi yapının
  içinden, (0, 0) olarak okundu. Test noktası da tam (0, 0)'dı ve şans eseri "dışarıda"
  çıktı. Geçersiz sınır testi artık beş farklı yönde nokta deniyor.
- **Bağımsız referans başka bir algoritma kullanmalı.** C ışın atma, Python dolanma
  sayısı, sınır tespiti için C aralık denetimi, Python iç çarpım.

**Faz 2.6 a bitti: kart komut alıyor** (K-023). Yankı kalktı. İki kanal
`firmware/app/channel/` üzerinden çalışıyor: `frame_rx` → `frame_decode` → sayaç (REPLAY).
Reddedilen her çerçeve kendi `STATUS` sayacını artırıyor, karttan cevap çıkmıyor. Oturum
kimliği açılışta donanım RNG'den (CubeMX'te RNG açıldı, CK48 saati HSI48: `139a189`). Kart
`HELLO`'yu oturum kurulana kadar 500 ms'de bir yayınlıyor, `HELLO_REQ`'e saniyede en fazla 2
kez cevap veriyor, `STATUS`'u saniyede bir gönderiyor, `HEARTBEAT`'e `HEARTBEAT_ACK` ile
cevap veriyor. Kart hep `HOLD`'da (durum makinesi c'de). `tools/link_test.py` 26 denetimi
iki kanalda yapıyor, 5 çalıştırmanın 5'inde de geçti.

**Faz 2.6 a'da öğrenilenler:**
- **Testi ikinci kez çalıştırmak da bir testtir.** İlk çalıştırma kusursuz geçti. İkincisinde
  kart `HELLO` yayınını kesmişti ve betik, oturum kimliğini öğrenmeden gelen bir `STATUS`'u
  doğrulamaya çalışıp düştü. Kartta hata yoktu, betikte vardı.
- **Port bir çerçevenin ortasında açılabilir.** Kart sürekli gönderdiği için betiğin ilk
  okuduğu parça yarım çerçeve olabiliyor (`COBS kodu çerçeve sonunun ötesini gösteriyor`).
  Rastgele görülüyordu. İlk ayraca kadar gelen baytlar atılınca kayboldu. Faz 3'teki
  köprünün de aynısını yapması gerekecek.
- **Okunan ama bakılmayan çerçeve kaybolmamalı.** Tek okumada birden fazla çerçeve gelebiliyor.
  Betik aradığını bulunca kalanını atıyordu. Yazarken fark edildi, bekleme listesi eklendi.
- **Derleyici uyarısı bir tasarım sorusuydu.** Release'te `hb.echo_pc_ms may be used
  uninitialized`: çözme fonksiyonunun sonucu yok sayılmıştı. Uyarı bastırılmadı, sonuç
  denetlendi.
- **RNG tam 48 MHz istiyor.** PLLQ 340 MHz'den 48'i üretemiyor (2, 4, 6, 8 ile bölünüyor).
  CK48 Clock Mux'ta HSI48 seçildi. HSI48 kristalsiz ve hassas değil, ama RNG rastgeleliği
  saatten değil gürültüden alıyor.

**HMAC anahtarı üretildi ve karta taşındı.** `tools/gen_key.py`, `secrets/hmac_key.bin`'i
(32 bayt, `os.urandom`) ve kartın başlığı `secrets/hmac_key.h`'yi üretiyor. İkisi de
depoya girmiyor. Kart anahtarı `firmware/app/auth/key`'den alıyor (`auth_key`), başlık
yoksa derleme açık bir mesajla duruyor. Doğrulama anahtar gösterilmeden yapıldı:
`HMAC(anahtar, "IKA anahtar denetimi")`'nin ilk 8 baytı (parmak izi) bilgisayarda ve
kartta aynı: `F6 17 EE 60 18 84 07 7C`. Anahtarı henüz hiçbir çerçeve kullanmıyor.

**Anahtar aşamasında öğrenilenler:**
- **Anahtar gösterilmeden denetlenebilir.** Sabit bir mesajın HMAC'i iki tarafta aynıysa
  anahtar da aynıdır. HMAC'ten anahtar geri çıkarılamadığı için bu 8 bayt belgeye yazılabilir.
- **Üretici anahtarın üzerine yazmamalı.** Yazsaydı betiği ikinci kez çalıştırmak kart ile
  bilgisayarı habersizce farklı anahtarlara düşürürdü. Belirti yalnızca "her çerçeve
  `err_auth`" olurdu.
- **Doğrulama kodu da yanılabilir.** Derlenmiş dosyadaki anahtar ilk iki karşılaştırmada
  "FARKLI" çıktı. Sebep objdump çıktısını yanlış ayrıştırmaktı (adres 7 hane, Release'te
  adres 4'ün katı değil). Ham bayt (`objcopy -O binary`) ile ikisi de "AYNI".
- **`#error`'dan sonra derleyici başka hatalar da sayar.** Kodun geri kalanı `#else` içine
  alınınca yalnızca asıl mesaj görünüyor.

**HMAC kartta ölçüldü** (`firmware/app/timing/dwt`, `app.c`'de geçici test, K-022). Girdi
`test_vectors.json`'daki VERDICT çerçevesi (en uzun yük, 23 bayt). Kartın hesapladığı
etiket vektördekiyle aynı: kriptografi kodu ARM'da da doğru. Süreler (net, `empty`
çıkarılmış, 170 MHz):

| | Release (`-Os`) | Debug (`-O0`) |
|---|---|---|
| A. Tam HMAC (4 blok) | 24 098 çevrim, **142 µs** | 131 403 çevrim, 773 µs |
| B. Hazırlanmış bağlam (2 blok) | 12 730 çevrim, **75 µs** | 65 977 çevrim, 388 µs |
| C. `hmac_tag_equal`: eşit / fark 0. bayt / fark 7. bayt | 140 / 140 / 140 | 343 / 343 / 343 |
| D. `memcmp` (kontrol): eşit / fark 0. bayt / fark 7. bayt | 147 / 48 / 139 | 144 / 45 / 136 |

En kısa komut (`VELOCITY_CMD`, 25 bayt) hatta 2,2 ms sürüyor. Hazırlanmış bağlam şimdilik
kullanılmıyor (K-022). **Kartta şu an Release derlemesi yüklü.** İşlev olarak Debug ile
aynı. CAN testi iki derlemede de geçti.

**Kartta ölçümden öğrenilenler:**
- **Kontrol deneyi olmadan "sabit zamanlı" sonucu boştur.** `hmac_tag_equal` üç durumda da
  aynı süreyi verdi. Bunun bir anlamı olması için ölçümün farkı görebildiği gösterilmeliydi:
  `memcmp`'te fark 0. bayttayken ve 7. bayttayken süreler arasında 91 çevrim var (doğru
  bayt başına ~13 çevrim).
- **Derleme seçeneği süreyi 5,5 kat değiştiriyor.** Tezde verilecek sayı, karta gerçekten
  yüklenen derlemenin sayısı olmalı ve seçeneği yanında yazılmalı.
- **Derleyici sabit zamanlılığı bozabilir, makine koduna bakılmalı.** `-Os`'ta
  `hmac_tag_equal` için üretilen kod `objdump` ile okundu: döngüde erken çıkış yok.
  Derleyici ya da seçenek değişirse ölçüm tekrarlanmalı.
- **`memcmp`'in farkı iki derlemede de 91 çevrim.** `memcmp` newlib-nano'dan önceden
  derlenmiş geliyor. Bizim `-O` seçimimiz onu etkilemiyor.
- **Kesmeler kapalıyken ölçüm çok kararlı.** Debug'da A için en kısa ile en uzun arası 12
  çevrim. Karşılaştırmalarda en uzun süre yalnızca her grubun ilk ölçümünde farklı
  (büyük ihtimalle flash önbelleği henüz dolmamış). Release'de B'nin aralığı 200 çevrim
  (%1,6), sebebi bulunmadı.

**Faz 2.6'nın kartsız kısmı bitti.** C çerçeveleyici üç parçada yazıldı, hepsi PC'de gcc
ile test ediliyor (`shared/protocol/tests/test_c_framer.py`, `c_driver.c`):
- `firmware/app/protocol/`: `crc16`, `cobs` (`da756d7`) ve `frame` (`fac14f0`):
  kodlama, COBS → CRC → tip/yön/kanal/uzunluk → etiket sırasıyla çözme, akışı `0x00`'da
  bölme (`frame_rx`).
- `firmware/app/auth/`: `sha256`, `hmac_sha256` ve sabit zamanlı `hmac_tag_equal`
  (`cfb1c5a`). Dışarıdan kod alınmadı (K-021).
- 147 test geçiyor. 17 çerçeve bayt bayt aynı, 7 bozuk çerçeve doğru türle reddediliyor,
  1 500 rastgele bozulmuş çerçevede ve 100 akışta C ile Python aynı kararı veriyor.
  Kart derlemesi 0 uyarı. Kodu henüz kimse çağırmıyor, flash boyutu değişmedi.

**Faz 2.6'da öğrenilenler (kartsız kısım):**
- **Testin kendisi de sınanmalı.** Kodun bir kopyasına bilerek hata konup testlerin
  yakalayıp yakalamadığına bakıldı (yön, kanal, etiket, oturum, kısa yük, taşma sınırı,
  etiketin yalnız ilk baytı: hepsi yakalandı).
- **Rastgele test nadir durumu ıskalar.** COBS çözme tamponu 42 bayta indirilince hiçbir test
  kırılmadı: rastgele bozma "COBS'u geçerli ama 42 bayttan uzun" çerçeveyi neredeyse hiç
  üretmiyor. Kritik kural için hedefli test eklendi. İlk rastgele COBS testinde de 500
  girdinin hepsi reddediliyordu, yani yalnız bir yol sınanıyordu.
- **Blok sınırları ayrı sınanmalı.** SHA-256 doldurmasının "uzunluğa yer kalmadı" sınırı bir
  bayt kaydırılınca `"abc"` yine doğru çıktı, 56 baytlık girdide program çöktü (tamponun
  dışına yazdı). 0–130 bayt her uzunluğu deneyen test bunu yakalar.
- **`-Werror` bazı hatalı kopyaları derletmez.** Denetim silinince parametre kullanılmamış
  kalıyor. Bu, testin yakaladığı anlamına gelmez; hatalı kopya derlenebilir yazılmalı.
- **SHA-256 sabitleri ezberden yazılmadı.** 72 sabit asal sayılardan Python'la türetildi.

**Faz 2.5 bitti.** Araç kanalı USART1'de, PC4/PC5 (kartta D1/D0), CP2102 modülüne bağlı
(`63d494d`). `agent_link`, iki kanala hizmet eden `serial_link` oldu (`8e9a382`). Kanal port
parametresiyle seçiliyor. Almayı durduran hat hataları türüne göre sayılıyor (`c765bac`).
İki kanal aynı anda 100 KB taşıdı, 0 fark. CAN testi geçmeye devam ediyor.

**Faz 2.5'te öğrenilenler:**
- **Akış kontrolü açık portta baytlar karta ulaşmıyor.** minicom'da donanım akış kontrolü
  açıkken yazılan `abcdef` CP2102'de bekledi, karta hiç gitmedi. Port akış kontrolü kapalı
  açılınca bu baytlar gönderilmedi, atıldı. Araç kanalı akış kontrolü kapalı açılmalı
  (`rtscts=False`).
- **DMA ile alırken her hat hatası almayı durdurur.** HAL bunu "blocking error" sayıyor
  (`stm32g4xx_hal_uart.c`, `HAL_UART_IRQHandler`). `serial_link` almayı yeniden başlatıyor.
  Bu yüzden her bozuk bayt ayrı bir hata olarak sayılıyor.
- **Hatanın türü `ErrorCode`'da, ama yeniden başlatma onu siliyor.** `HAL_UART_Receive_DMA`
  bu alanı sıfırlıyor. Tür yeniden başlatmadan önce okunmalı.
- **Kasıtlı hat hatası üretmek kolay.** Portu yanlış hızda (9600) açıp `0x00` göndermek
  yeterli: kart durma bitinin yerinde 0 görür ve bu bir çerçeve hatasıdır (FE).
- **Araç kanalında 97 hat hatası görüldü, yeniden üretilemedi.** Sayaç o sırada türü
  ayırmıyordu. Denenenler: 10 s boşta durma, portu 3 kez açıp kapama, CP2102'yi çıkarıp
  takıp 30 s bekleme, minicom'un akış kontrolü davranışını taklit etme, 2 × 100 KB yük.
  Hiçbiri sayacı artırmadı. Hatalar büyük ihtimalle kurulum sırasında bir kez oldu. Veri
  akarken hiç kayıp olmadı. Bir tahmin (kanıtı yok): kartın TX pini, USB'si takılı olmayan
  CP2102'yi sinyal teli üzerinden yarım besliyor ve çip bu arada anlamsız sinyal üretiyor.
  Tekrar olursa ilk bakılacak yer tür sayaçları (aşağıda "Karttan RAM okuma").

**Faz 2.4 bitti.** FDCAN1 ve FDCAN2 CubeMX'te Normal modda (`fbf4fc9`). Çerçeveler
FDCAN1 → SN65HVD230 → CANH/CANL → SN65HVD230 → FDCAN2 yolundan geçiyor. `app.c`'deki test
gerçek hatta uyarlandı (`ec731ce`), hâlâ geçici. FDCAN1 DRIVE → GOAL → HALT verdi, FDCAN2
DRIVE, HALT, GOAL sırasıyla aldı. TELEMETRY ters yönde sağlam geldi, dört hata sayacı da 0.
`can_link` değişmedi. Filtre 1 Normal modda beklendiği gibi kurulmuyor.

**Faz 2.4'te öğrenilenler:**
- **Normal modda ACK için alıcının da hazır olması gerekiyor.** İç döngüde ACK'yi birim kendine
  veriyordu. Gerçek hatta ACK'yi FDCAN2 veriyor. Senkronize olmamış bir alıcı ACK vermez ve
  gönderen TEC'i 8 artırır. Test bu yüzden göndermeden önce iki birimin de boşa çıkmasını
  bekliyor.
- **FIFO kontrol deneyi (Faz 2.3'teki B) gerçek hatta yapılamaz.** FDCAN1'in filtresi araçtan
  komut kimliği almaz. Deney iç döngüde yapılmıştı (K-019). Tamponun seçimi kabloya bağlı değil.
- **LEC ve REC hatanın türünü ayırt ediyor.** Kopuk hat denemesinde (CANH sökülü) `LEC = 3`
  (ACK hatası) ve REC = 0 okundu: bu "karşıda cevap veren yok" demek. Bozuk sinyal (ters bağlı
  tel, kesik temas) bit/stuff hatası (`LEC` 1, 4, 5) ve artan REC ile görünür. Hat sorunu
  çıkarsa ilk bakılacak yer `PSR` (`0x40006444`, `0x40006844`) ve `ECR` (`…40`, `…840`).
- **CubeMX `.ioc`'ta `functionlistsort`'u kendisi tamamladı.** Bu listeye Faz 2.3'te
  `MX_FDCAN2_Init` eklenmemişti. `main.c` değişmedi, yani çağrı zaten vardı.

**Faz 2.3'te öğrenilenler:**
- **Kuyruk modunda `HAL_FDCAN_GetTxFifoFreeLevel()` hep 0 döner.** `TXFQS.TFFL` alanı yalnızca
  FIFO'da anlamlı. İlk denemede bekçi bu yüzden hiçbir mesaj gönderemedi. Kartın yazmacından
  okunarak doğrulandı: FDCAN1 `TXFQS = 0`, FDCAN2 `TXFQS = 0x00010103` (TFFL = 3), iki tampon da
  boşken. Doluluk iki modda da geçerli olan `TFQF` bitinden soruluyor.
- **Sıra testi zamanlamaya duyarlı.** Başlatılan birim hatta 11 bit sessizlik görene kadar
  (~22 µs) gönderemez. O sırada üç mesaj da tamponda birikir ve HALT DRIVE'ın da önüne geçer.
  Test bu yüzden önce birimin boşa çıkmasını, sonra DRIVE'ın hatta görünmesini
  (`HAL_FDCAN_GetProtocolStatus`, `Activity`) bekliyor.

**Sırada:** Faz 3 (plan §5): simülasyon, harita, Nav2, köprü. Önce disk yeri ve Gazebo kararı.

## Bitenler

- [x] Disk temizliği: 4,3 GB → 11 GB (sonraki kurulumlarla şu an 2,8 GB, bkz. engeller)
- [x] Proje klasör yapısı + git deposu + ilk commit
- [x] Ubuntu 22.04.5 LTS · ROS 2 Humble · Nav2 (30 paket) · teleop_twist_keyboard
- [x] Git, VS Code, Claude Code
- [x] `minicom`, `python3-serial`, `pulseview`, `sigrok-firmware-fx2lafw`, `unzip`
- [x] RTAB-Map (`ros-humble-rtabmap-ros`, 14 paket)
- [x] STM32CubeIDE 2.2.0 → `/opt/st/stm32cubeide_2.2.0`
- [x] STM32CubeMX 6.18.1 → `~/STM32CubeMX`. **CubeIDE 2.0'dan itibaren CubeMX IDE'nin
      içinde gelmiyor.** Planın 3.6'daki "File → New → STM32 Project" adımı artık yok.
      Proje CubeMX'te üretilip CubeIDE'ye aktarılıyor
- [x] ST-LINK udev kuralları kuruldu (49-stlinkv1/v2/v2-1/v3.rules)
- [x] `dialout` grubuna eklendi ve oturumda doğrulandı (2026-09-24)
- [x] GitHub'da `bitirme-ika-otonom` özel deposu açıldı
- [x] Parçalar geldi (2026-09-24): Robiz.net, 656,16 TL, liste `docs/malzeme-listesi.md`'de.
      Mantık analizörü ertelendi (K-009)
- [x] **Faz 0 tamam:** LED testi (plan 3.6). CubeMX olmadan, terminalden, doğrudan
      yazmaçlarla yazılıp yüklendi. LD2 500 ms'de bir yanıp söndü
- [x] **Faz 1 tamam:** okuma listesi · `docs/RULES.md` (K-010 … K-013) ·
      `docs/protocol.md` (K-014) · `messages.yaml` (17 mesaj), kod üreticisi, `frame.py`,
      80 test · tekrar sayısı (K-015)
- [x] **Faz 2.1 tamam:** CubeMX projesi (`5d3878e`, dokunulmamış hâl), `app/` katmanı
      (`9214910`)
- [x] **Faz 2.2 tamam:** LPUART1 + DMA CubeMX'te (`dbc454f`), `agent_link` ve yankı testi
      (`45231e1`)
- [x] **Faz 2.3 tamam:** FDCAN1/2 CubeMX'te (`05d9469`), `can_link` ve iç döngü testi
      (`c0c0d9d`)
- [x] CAN modüllerinin pin başlıkları lehimlendi. PA11/PA12 ve PB12/PB13'ün kart üzerindeki
      lehim köprüleriyle çakışmadığı UM2505'ten kontrol edildi. Kablolama kontrol edildi
- [x] **Faz 2.4 tamam:** FDCAN1/2 Normal modda (`fbf4fc9`), gerçek hat testi (`ec731ce`)
- [x] Kopuk hat denemesi (öğrenmek için): CANH sökülünce test beklenen şekilde kaldı,
      tel takılınca yeniden geçti
- [x] **Faz 2.5 tamam:** USART1 + DMA CubeMX'te (`63d494d`), `serial_link` (`8e9a382`),
      hat hatası türü sayaçları (`c765bac`)
- [x] **Faz 2.6 kartsız kısmı tamam:** CRC-16 ve COBS (`da756d7`), SHA-256 ve HMAC
      (`cfb1c5a`), çerçeve (`fac14f0`). 147 test
- [x] **Faz 2.6 kartta ölçüm tamam:** DWT çevrim sayacı (`timing/dwt`), HMAC süresi ve
      sabit zamanlı karşılaştırma ölçüldü (K-022)
- [x] **HMAC anahtarı:** `tools/gen_key.py`, `firmware/app/auth/key`. Parmak izi kartta ve
      bilgisayarda aynı
- [x] **Faz 2.6 tamam:** a komut alma (K-023), b coğrafi sınır (K-024), c uçtan uca karar ve
      d kalp atışı (K-025). CubeMX: RNG (`139a189`), TIM6 ve PA8 (`11d6ef0`, K-026)

## Sırada

- [x] **Kablo çekme testi** (K-029): 500–501 ms, 20 Hz, `HOLD`. Geri takmada reset bulgusu
- [ ] **Besleme varsayılana (Esra, donanım):** USB'leri çıkar, JP5'i 5V_STLK'e al, CN7 pin 6'daki
      E5V telini çıkar
- [x] **Faz 3 öncesi kararlar:** Gazebo Fortress + TurtleBot 4 (K-027), disk engeli kalktı (K-028)
- [x] **Faz 3** (plan onaylandı 2026-10-05, bitti 2026-10-08, `v0.3.0`):
  - [x] **3.0 Kurulum** (K-030): `ros-gzharmonic` kaldırıldı, Fortress + TurtleBot 4 simülatörü
        kuruldu, `warehouse` dünyası açılıyor (ilk açılışta bir süre siyah ekran, sonra düzeldi).
        Konular: `/oakd/rgb/preview/image_raw` (320×240), `/oakd/rgb/preview/depth` (32FC1),
        `/oakd/rgb/preview/camera_info` (çerçeve `oakd_rgb_camera_optical_frame`), `/scan`
        (~28 Hz), `/odom`, `/tf`, `/clock`, aracın hız girişi `/cmd_vel`. Dünyalar: `warehouse`,
        `depot`, `maze`
  - [x] **Deney sahası `ika_saha`** (K-032, yukarıda): Blok 1–5 ✅ (2026-10-06). Saha simde
        açılıyor, yasak bölgeler zeminde görünüyor, hız ölçülen %46 (hazır dünyalar ekrandan
        ~%30 okunmuştu, aynı yöntemle ölçülmedi)
  - [ ] **Araç İKA'ya geçiyor** (K-034):
    - [x] a. Model depoya: `ika_sim/models/ika_arac/` (Fortress'e çevrilmiş, kaynak ve üç değişiklik
          `model.sdf`'nin başındaki yorumda; yorum hariç simde denenen kopyayla bayt bayt aynı)
    - [x] b. Saha 32 × 20 m (K-035): 25 bariyer, yeni yerleşim, asfalt 33 × 21 m; simde görüldü
    - [x] c. İKA simde (2026-10-06): dünyaya Sensors/Imu/Contact ve İKA `<include>`'u,
          `config/bridge.yaml` (9 konu), başlatma dosyasında 4 sabit `tf`, modelde 4.
          değişiklik (kamera `camera_optical_frame`). Denetlendi: konular akıyor (lidar,
          kamera, derinlik 10 Hz; IMU 100 Hz; odom, `/tf` ~48 Hz), çerçeve etiketleri doğru,
          `tf` ağacı `odom → base_link → {lidar_link, imu_link, camera_link → camera_optical_frame}`,
          hız köprüyle %100 (2 × 20 s), klavyeyle sürüldü, RViz'de lidar ve kamera görüldü
  - [x] **3.1 Harita** (2026-10-06, K-036): `ika_nav/launch/mapping.launch.py` (RTAB-Map, kamera +
        lidar, tekerlek odometrisi, `Grid/Sensor 0`, `Reg/Strategy 1`, `RGBD/NeighborLinkRefining`,
        `Reg/Force3DoF`), harita `ika_nav/maps/ika_saha.pgm`/`.yaml` (5 cm, 34,6 × 22,7 m,
        köşe (−4,38, −12)). Klavyeyle ~80 m'lik tur, başlangıçta bitti. Sonuçlar:
        - Rota ortasında konum hatası RTAB-Map 1,9 m / 22°, yalnız odometri 11,0 m / 78°.
          Başlangıca dönünce RTAB-Map 0,10 m / 7,6°, odometri 13,8 m / 80°.
        - Graf (rota ortasında): 129 düğüm, 86 komşuluk, 7 döngü kapatma, 35 yakınlık bağı.
        - Koordinat denetimi: konteyner boyu doğru (gerçek 6,06 × 2,44, haritada 6,15 × 2,55), ama
          +0,55 m x, −0,25 m y kaymış; tanklar 0,7–0,8 m güneyde. Harita başlangıç etrafında
          ~2° dönmüş (20 m'de ~0,7 m). "Harita = dünya" (K-032) en çok ~0,8 m hatayla tutuyor.
        - Kaydetme: `map_saver_cli -t /rtabmap/map` (konu `/map` değil).
        - Karar (K-036): harita kabul; 3.2'de yasak bölgelere ve izinli alana ≥ 1 m pay.
  - [x] **3.2 Saha tanımı ve Nav2** (K-037, K-038). Bitti: RViz "2D Goal Pose" ile araç hedefe gidiyor,
        maske Nav2'de, kart aynı bölgeleri biliyor
    - [x] a. Saha tek dosyada (2026-10-07): `shared/site/ika_saha.yaml` (gerçek sınırlar, `margin_m`
          1,0, 3 yasak bölge, 5 adlı güvenli nokta) → `tools/gen_site.py` (`--check` var) →
          `firmware/app/site/site_data.c` + `ika_nav/maps/ika_saha_keepout.pgm/.yaml`. Pay
          güvenli tarafa yuvarlanır (izinli alan x −159…2759, y ±859 cm). Testler:
          `shared/site/tests`, 19 test; maskenin 314 622 hücresi kartın gerçek C koduyla
          karşılaştırıldı, fark 0. Kasıtlı 3 hatanın 3'ü yakalandı. Güney koridoru payla kapandı.
          **Ölçüm:** haritanın 2°'lik dönmesi yüzünden kuzeydoğu köşesinde haritadaki bariyer
          izinli alanın ~0,25 m içinde (hata orada ~1,2 m; K-036'nın 0,8 m'si konteyner ve
          tanklardan). Kart orada ulaşılamaz hedef kabul edebilir, Nav2 reddeder.
          **Uyarı:** `site_data.c` değişti; `tools/decision_test.py` hâlâ eski deneme sahasını
          bekliyor, kartta eski derleme var (3.2c).
    - [x] b. Nav2 (2026-10-07, K-038; deneme 3 ve `use_sim_time` 2026-10-08): `ika_nav/config/nav2_params.yaml`,
          `ika_nav/launch/navigation.launch.py`. AMCL + `ika_saha.pgm`, NavFn, Regulated Pure Pursuit,
          araç izi 1,78 × 1,15 m + 0,3 m pay. Costmap'ler: statik harita + keepout katmanı +
          şişirme (1,5 m); lidar katmanı yok. Ara katman CycloneDDS (`~/.bashrc`).
          - Deneme 1 (konteyner arkası (8, 7,6)): geçti. AMCL hedefe 0,28 m; AMCL'nin gerçeğe göre
            hatası 0,36 m / 3,9°.
          - Deneme 2 (kazının doğusu (25,9, −2,65)): geçti, konteynerin ARKASINDAN dolandı (güney
            koridoru ve konteyner–kazı darboğazı kapalı). AMCL hedefe 0,23 m; gerçek konum AMCL'den
            1,4 m kuzeyde (haritanın 2°'lik dönmesi, uzak uçta; K-037'deki ~1,2 m ile tutarlı).
          - Sırada deneme 3: yasak bölgenin içine hedef → Nav2 plan bulamamalı.
          - Yapılacak: `ika_sim` başlatma dosyasındaki 4 sabit `tf` yayıncısına `use_sim_time`
            (bilgisayar saatiyle damgalı; sebep değil ama tutarsızlık).
          Bu sonuca gelene kadar değişenler ve nedenleri: aşağıda "3.2b'de öğrenilenler".
    - [x] c. Kart: firmware derlenir, `decision_test.py` YAML'dan okur, karta yükleme (onayla)
          (2026-10-08, `bb64cd9`, `decision_test` kartta geçti)
  - [x] **3.3 Köprü (`guard_bridge`)** (2026-10-08, K-040, K-041): `docs/protocol.md` §10. `tools/`'taki `Link` mantığı
        kullanılır. Kartta asgari `VELOCITY_CMD` → `DRIVE` aktarması (K-031). Bitti (plan
        belgesi): RViz hedefi karttan geçip araca ulaşıyor, izinli bölge dışındaki hedef
        reddediliyor, kartın kablosu çekilince araç duruyor
- [ ] **Faz 4** (plan onaylandı 2026-10-13; ayrıntı yukarıda "Sırada"):
  - [x] **4.0 Hazırlık** (2026-10-14): NVIDIA sürücüsü, Ollama, model seçimi (K-045), ivme (K-046)
  - [ ] **4.1 Kart, kalan kurallar:** LIMIT ve `VELOCITY_CMD` kırpma (asgari aktarma Faz 3'te,
        K-031), `WAIT_CMD`/`SPEED_LIMIT_CMD`/`STOP_CMD`, FRESHNESS (zaman eşitlemesi), araç
        konumunun coğrafi sınır denetimi, RECOVERY (üst üste 5 içerik reddi), K-042 `HALT(0)`,
        CONSISTENCY
  - [ ] **4.2 Köprü:** K-042 hedef iptali, görev komutları, gerekçe konusu
  - [ ] **4.3 Ajan:** araçlar, yer isimleri (K-044), ret döngüsü (≤ 3 deneme)
  - [ ] **4.4 Uçtan uca** → `v0.4.0`

## Doğrulanmış testler

- [x] Kart: **NUCLEO-G474RE, MB1367/C**, CN1 = micro-USB, **STLINK-V3** (FW V3J9M3),
      SWD bağlantısı, 3,30 V
- [x] Seri portlar: ajan kanalı `/dev/ttyACM0`, araç kanalı (CP2102) `/dev/ttyUSB0`,
      ikisi de açılabiliyor
- [x] LED testi (plan 3.6). İlk denemede JBL kablosunun veri teli olmadığı anlaşıldı,
      veri kablosuyla çalıştı
- [x] Faz 2.1 firmware: 27 kaynak dosya, 0 uyarı, flash 10 720 B. Kartta çalışıyor
- [x] Faz 2.2 firmware: 0 uyarı, flash 18 424 B. Kartta çalışıyor, LD2 nabzı sürüyor
- [x] Faz 2.3 firmware: 0 uyarı, flash 23 828 B. İç döngü testi geçti:
      kuyruk modu DRIVE, HALT, GOAL. FIFO modu DRIVE, GOAL, HALT. TELEMETRY sağlam, bayt farkı 0,
      TEC/REC 0 (RAM'den okundu)
- [x] Faz 2.4 firmware: 0 uyarı, flash 23 796 B. Gerçek hat testi geçti: FDCAN2'ye
      DRIVE, HALT, GOAL (0x110, 0x100, 0x120) sırasıyla geldi. TELEMETRY FDCAN1'e sağlam geldi,
      bayt farkı 0, TEC/REC dördü de 0 (RAM'den okundu, `can_test_result` = `0x20000264`)
- [x] Kopuk hat (CANH sökülü): `fail_step = 14`, iki birimde TEC = 128, REC = 0.
      `PSR = 0x77B`: `LEC = 3` (ACK hatası), `EP = 1`, `EW = 1`, `BO = 0`. TEC 128'de duruyor,
      çünkü error passive gönderici ACK hatasında TEC'i artırmaz. Tel takılınca yeniden geçti,
      `PSR = 0x708` (`LEC = 0`, boşta, error active), `ECR = 0`
- [x] Faz 2.5 firmware: 0 uyarı, flash 24 672 B. Araç kanalında elle yankı ve 100 KB yük
      testi, 0 fark. İki kanal aynı anda 100 KB: ajan 11 411 B/s, araç 10 544 B/s, 0 fark
- [x] Hat hatası sayaçları: araç kanalına 9600 baud'da 5 × `0x00` gönderildi. Sonuç
      restarts 5, frame 5, noise/overrun/other 0. Ajan kanalında sayaçların hepsi 0.
      Ardından 115200'de yankı çalıştı
- [x] Coğrafi sınır (gcc, ASan ve UBSan ile, PC'de): 45 test, 51 462 rastgele nokta Python
      referansıyla aynı. Kasıtlı hata konmuş 13 kopyanın 13'ü yakalandı. Kart derlemeleri 0
      uyarı, kod henüz çağrılmadığı için flash boyutu değişmedi
- [x] C çerçeveleyici (gcc, PC'de): 147 test. CRC `"123456789"` → `0x29B1`, SHA-256 NIST
      girdileri ve 1 milyon `a`, HMAC RFC 4231'in 7 örneği, protocol.md §4.4'teki etiket
      `06 1A 85 7A 51 0A AA 4E`. Çalıştırmak için: `python3 -m pytest shared/protocol/tests firmware/tests`
- [x] HMAC kartta (Faz 2.6, `hmac_test_result`): `tag_ok = 1`, iki derlemede de. Release
      firmware 0 uyarı, flash 15 616 B. Debug firmware 0 uyarı, flash 28 144 B. Süreler
      yukarıdaki tabloda. CAN testi iki derlemede de geçti (sıra `0x110, 0x100, 0x120`,
      TEC/REC 0)
- [x] Anahtar (`key_check_result`): kartın parmak izi `F6 17 EE 60 18 84 07 7C`,
      `gen_key.py`'ninkiyle aynı. Derlenmiş dosyadaki `auth_key` iki derlemede de
      `hmac_key.bin` ile bayt bayt aynı. Anahtar başlığı yokken derleme tek mesajla duruyor.
      Release firmware 0 uyarı, flash 15 748 B. HMAC ve CAN testleri geçmeye devam ediyor
- [x] Faz 2.6 c/d firmware: Debug 0 uyarı, flash 39 520 B; Release 0 uyarı, 21 268 B.
      `python3 tools/decision_test.py` 26 denetim, `link_test.py` 25 denetim, ikisi de art arda
      çalıştırmalarda Debug ve Release'te geçti. Karar süresi Release 169–177 µs, Debug
      853–886 µs. `guard_can_tx_full`, `vehicle_node_errors` 0. `guard` PC'de 18 test,
      kasıtlı hata konmuş 14 kopyanın 14'ü yakalandı
- [x] Faz 2.6 a firmware (Debug): 0 uyarı, flash 32 568 B. Release 0 uyarı, 17 600 B.
      `python3 tools/link_test.py`: 26 denetim geçti, 5 çalıştırmanın 5'inde. Ajan kanalında
      `HELLO` (şema `0xB12F26D8`, `HOLD`), imzalı `HEARTBEAT` → `HEARTBEAT_ACK`. Tekrar
      oynatılan, yanlış anahtarla ve başka oturumla imzalanan, biti bozuk, ajan kanalından
      gelen `TELEMETRY` ve 70 baytlık çerçeve: cevap yok, `err_replay` +1, `err_auth` +2,
      `err_crc` +1, `err_type` +1, `err_framing` +1. 5 `HELLO_REQ` → 1 `HELLO`. Araç kanalında
      oturum kimliği aynı, `TELEMETRY` kabul, `HEARTBEAT` `err_type`. CAN testi geçmeye devam ediyor
- [x] Kablo çekme (`tools/unplug_test.py`, Release firmware, E5V beslemesi): üç
      çalıştırmada kopma bölümünün bütün denetimleri geçti, sıfır hıza 500 / 500 / 501 ms
      (kartın saati). Geri takma denetimleri üçünde de kaldı: kart yeniden başlıyor (K-029)
- [x] Ajan kanalında elle yankı (minicom, `/dev/ttyACM0`, 115200)
- [x] Ajan kanalında yük testi (`tools/echo_test.py`, **Faz 2.6 a'dan beri kartta yankı yok**,
      betik ancak `139a189` ve öncesindeki bir firmware ile çalışır): 102 400 / 102 400 bayt, 0 fark,
      11 422 B/s (hat sınırının %99,1'i). Dairesel tampon ~400 kez başa döndü
- [x] CAN modülü: üzerinde `121` (120 Ω) sonlandırma direnci görüldü. Ek direnç gerekmiyor
- [x] Protokol: 80 test, C↔Python bayt eşitliği dahil

## Derleme ve yükleme

Depo kökünden, CubeIDE penceresini açmadan:

```bash
# Anahtar başlığı. Depo yeni klonlandıysa bir kez. Anahtar varsa korunur
python3 tools/gen_key.py
# Derle. Çalışma alanı depo DIŞINDA. İlk seferde -import de verilir
/opt/st/stm32cubeide_2.2.0/headless-build.sh -data ~/STM32CubeIDE/ws_headless \
    -import "$PWD/firmware" -build firmware/Debug
# Sonraki derlemeler
/opt/st/stm32cubeide_2.2.0/headless-build.sh -data ~/STM32CubeIDE/ws_headless -build firmware/Debug

# Karta yükle. ONAY GEREKİR (CLAUDE.md)
"$(find /opt/st/stm32cubeide_2.2.0/plugins -name STM32_Programmer_CLI -type f)" \
    -c port=SWD -w firmware/Debug/firmware.elf -v -rst
```

- `-v` yazılanı geri okuyup doğrular, `-rst` kartı yeniden başlatır.
- Derleme `No Project matched "firmware/Debug"` uyarısı verip hiçbir şey yapmazsa proje
  çalışma alanında kayıtlı değildir. Komutu `-import "$PWD/firmware"` ile yeniden çalıştır
  (2026-09-27'de oldu).
- **CubeIDE penceresiyle çalışırken** ayrı bir çalışma alanı seç (yine depo dışında).
  Projeyi **File → Import → Existing Projects into Workspace** ile `firmware/`'dan aktar,
  **"Copy projects into workspace" işaretini kaldır.**
- **Seri portların kalıcı adları:** `ttyACM0`/`ttyUSB0` numaraları takma sırasına göre
  değişebilir. Köprü şunları kullanmalı:
  - ajan: `/dev/serial/by-id/usb-STMicroelectronics_STLINK-V3_003B00163235511037333439-if02`
  - araç: `/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0`

**Karttan RAM okuma** (çalışan programın değişkenleri, hata ayıklayıcı açmadan):

```bash
# Değişkenin adresi ve boyutu (her derlemede değişebilir)
"$(find /opt/st/stm32cubeide_2.2.0/plugins -name arm-none-eabi-nm -type f | head -1)" \
    -S firmware/Debug/firmware.elf | grep can_test_result
# Çalışan karta dokunmadan oku. Salt okuma, onay gerekmez
"$(find /opt/st/stm32cubeide_2.2.0/plugins -name STM32_Programmer_CLI -type f)" \
    -c port=SWD mode=HOTPLUG -r32 <adres> <boyut>
```

**Seri hat hatası sayaçları.** Her kanalın yapısı (`agent`, `vehicle`) içinde, başlangıçtan
`0x148` bayt sonra 5 × 4 bayt. Sırasıyla: restarts, frame (FE), noise (NE), overrun (ORE),
other.

```bash
"$(find /opt/st/stm32cubeide_2.2.0/plugins -name arm-none-eabi-nm -type f | head -1)" \
    -S firmware/Debug/firmware.elf | grep -E " (agent|vehicle)$"
# <yapının adresi + 0x148>'den 20 bayt oku. c765bac'te: ajan 0x20000538, araç 0x20000694
```

**Faz 2.6'nın RAM değişkenleri** (adresleri `arm-none-eabi-nm -S <elf> | grep <ad>` ile):
- `goto_timing` (16 bayt): count, last, min, max, çevrim (170 MHz'de 5,9 ns). Karar süresi.
- `guard_can_tx_full` (4 bayt), `vehicle_node_errors` (8 bayt: bilinmeyen CAN kimliği,
  FDCAN2 tamponu dolu). Hepsi 0 olmalı.
- `can_test_result`: açılıştaki Faz 2.4 CAN testi, nabız LED'i buna bağlı.
- Faz 2.6'nın ara ölçümleri (`hmac_test_result`, `key_check_result`) `abf1b7e`'de kaldırıldı.
  Kodları git geçmişinde: `1e803bc`, `907aaff`.

## Açık sorular / kararsız konular

| Konu | Durum | Ne zaman karar verilecek |
|---|---|---|
| LPUART1: BSP üzerinden mi, CubeMX'te çevre birimi olarak mı | ✅ K-017: CubeMX'te çevre birimi, alma DMA ile | — |
| Gazebo: Fortress + TurtleBot 4 mü, mevcut Harmonic'te kendi modelimiz mi | ✅ K-027: Fortress + TurtleBot 4 | — |
| LLM model seçimi (araç çağırma şart) | **Açık** | Faz 4 başında |
| Senaryo başına tekrar sayısı | ✅ K-015: LLM senaryolarında 20, arızada 10 | — |
| Araç kanalındaki 97 hat hatasının sebebi | **Açık**, yeniden üretilemedi | Tekrar görülürse, tür sayaçlarına bakılarak |
| Ana döngü takılırsa (kalp atışı kesmeyle algılanır, tepki ana döngüde) | **Açık**, bağımsız bekçi zamanlayıcısı (IWDG) olabilir (K-025) | Faz 4–5, kapsam kuralına göre |
| PA8 hangi sokette | ✅ UM2505 Tablo 15–16: CN9 pin 8 (Arduino D7), ayrıca CN10 pin 23 | — |
| Kablo geri takılınca ST-LINK kartı resetliyor, JP3'süz yol | **Açık**, birikmiş bayraklarda `SFTRSTF` (K-029) | Gerekirse, Faz 5 tekrarlarından önce |

## Bilinen engeller

- **Simülasyon yavaş:** gerçek zamanın ~%28–33'ü (TurtleBot 4 + kamera + lidar, Intel iGPU).
  Kartın gerçek zamanlı kuralları (kalp atışı) ile simülasyon saati arasındaki fark 3.3'te
  düşünülmeli. NVIDIA sürücüsü kurulursa iyileşebilir.
- **NVIDIA sürücüsü kurulu değil.** Kartta RTX 3050 Mobile var (~4 GB VRAM) ama sistem
  Intel iGPU kullanıyor, `nvidia-smi` yok. Faz 4'te yerel LLM için sürücü kurulmalı;
  kurulmazsa model CPU'da çok yavaş kalır ve API'ye geçmek gerekebilir.
- **Gazebo sürüm çakışması.** Sistemde Harmonic (gz-sim8) var; TurtleBot 4'ün Humble
  simülatörü Fortress'e bağımlı. Gazebo'nun iki sürümü yan yana durur ama ROS köprü
  paketleri durmaz (K-030). `ign`/`gz` komutları ve ortam değişkenleri karışabilir.
- **Kablo geri takılınca kart yeniden başlıyor** (K-029). Geri takma sonrası `HOLD` mandalı
  ve kopma sırasındaki ajan kanalı hata sayaçları fiziksel testte ölçülemiyor.

## Nerede takıldım

(boş)
