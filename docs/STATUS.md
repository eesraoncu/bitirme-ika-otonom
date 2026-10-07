# Proje Durumu

> Bu dosya her çalışma oturumunun **başında okunur**, **sonunda güncellenir**.
> Claude Code ile çalışırken ilk iş: bu dosyayı ve `docs/DECISIONS.md`'yi okut.

**Son güncelleme:** 2026-10-07
**Bulunduğumuz faz:** Faz 3. 3.0 kurulum bitti, deney sahası (K-032) Blok 1–5 bitti. Araç İKA (K-034), saha 32 × 20 m (K-035). 3.1 harita bitti (K-036). 3.2a saha tanımı bitti (K-037). 3.2b Nav2 çalışıyor (K-038): deneme 1 ve 2 geçti, sırada deneme 3, sonra 3.2c (kart)

---

## Şu an ne yapılıyor

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
- [ ] **Faz 3** (plan onaylandı, 2026-10-05):
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
  - [ ] **3.2 Saha tanımı ve Nav2** (K-037). Bitti: RViz "2D Goal Pose" ile araç hedefe gidiyor,
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
    - [ ] b. Nav2 (2026-10-07, K-038): `ika_nav/config/nav2_params.yaml`,
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
    - [ ] c. Kart: firmware derlenir, `decision_test.py` YAML'dan okur, karta yükleme (onayla)
  - [ ] **3.3 Köprü (`guard_bridge`):** `docs/protocol.md` §10. `tools/`'taki `Link` mantığı
        kullanılır. Kartta asgari `VELOCITY_CMD` → `DRIVE` aktarması (K-031). Bitti (plan
        belgesi): RViz hedefi karttan geçip araca ulaşıyor, izinli bölge dışındaki hedef
        reddediliyor, kartın kablosu çekilince araç duruyor
- [ ] Faz 4'e kalanlar (bilerek): FRESHNESS (zaman eşitlemesi), LIMIT, CONSISTENCY,
      RECOVERY durumu (üst üste 5 içerik reddi), `WAIT_CMD`/`SPEED_LIMIT_CMD`/`STOP_CMD`/
      `VELOCITY_CMD` kırpma (asgari aktarma Faz 3'te, K-031), araç konumunun coğrafi sınır denetimi
- [ ] Ollama kurulumu (model seçimi Faz 4'te)

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
