# Proje Durumu

> Bu dosya her çalışma oturumunun **başında okunur**, **sonunda güncellenir**.
> Claude Code ile çalışırken ilk iş: bu dosyayı ve `docs/DECISIONS.md`'yi okut.

**Son güncelleme:** 2026-09-28
**Bulunduğumuz faz:** Faz 2, STM32 tarafı (2.3 tamam, sırada 2.4)

---

## Şu an ne yapılıyor

**Faz 2.3 bitti.** FDCAN1 ve FDCAN2 CubeMX'te iç döngü modunda kuruldu (K-019). Kanal
kodu `firmware/app/links/can_link` altında ve kalıcı. `app.c`'deki test geçici. Aynı üç mesaj
DRIVE → GOAL → HALT sırasıyla verildi, GOAL ile HALT DRIVE hattayken. Kuyruk modundaki FDCAN1
DRIVE, HALT, GOAL; FIFO modundaki FDCAN2 DRIVE, GOAL, HALT sırasıyla gönderdi. TELEMETRY sağlam
geri geldi, hata sayaçları 0.

**Faz 2.3'te öğrenilenler:**
- **Kuyruk modunda `HAL_FDCAN_GetTxFifoFreeLevel()` hep 0 döner.** `TXFQS.TFFL` alanı yalnızca
  FIFO'da anlamlı. İlk denemede bekçi bu yüzden hiçbir mesaj gönderemedi. Kartın yazmacından
  okunarak doğrulandı: FDCAN1 `TXFQS = 0`, FDCAN2 `TXFQS = 0x00010103` (TFFL = 3), iki tampon da
  boşken. Doluluk iki modda da geçerli olan `TFQF` bitinden soruluyor.
- **Sıra testi zamanlamaya duyarlı.** Başlatılan birim hatta 11 bit sessizlik görene kadar
  (~22 µs) gönderemez. O sırada üç mesaj da tamponda birikir ve HALT DRIVE'ın da önüne geçer.
  Test bu yüzden önce birimin boşa çıkmasını, sonra DRIVE'ın hatta görünmesini
  (`HAL_FDCAN_GetProtocolStatus`, `Activity`) bekliyor.

**Sırada Faz 2.4: iki FDCAN birimi gerçek hat üzerinden.** Önce lehim (aşağıda, "Sırada").

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

## Sırada

- [ ] **Faz 2.4:** FDCAN1 → SN65HVD230 → CANH/CANL → SN65HVD230 → FDCAN2.
      - CubeMX'te iki birimin Mode'u **Normal** yapılıp yeniden üretilecek. `can_link`'in iç döngü
        filtresi (filtre 1) bu durumda kendiliğinden kurulmaz.
      - Kablolamadan önce PA11/PA12 (FDCAN1) ve PB12/PB13 (FDCAN2) pinlerinin kart üzerindeki
        lehim köprüleriyle çakışıp çakışmadığına UM2505'ten bakılacak.
      - `app.c`'deki test gerçek hat için uyarlanacak: FDCAN1 gönderir, FDCAN2 alır, TELEMETRY
        ters yönde.
- [ ] **CAN modüllerinin pin başlıklarını lehimle (Faz 2.4'ten önce şart).** Lehimsiz
      temas kesik kesik olur ve CAN hatası sanılır. Lehim sırasında ikinci modülde de
      `121` (120 Ω sonlandırma) olup olmadığına bak
- [ ] **Faz 2.6'nın kartsız kısmı:** `firmware/app/protocol/` altında C çerçeveleyici.
      `test_vectors.json`'a karşı gcc ile test. Etiket sabit zamanlı karşılaştırılmalı
- [ ] HMAC anahtarını üret: `secrets/hmac_key.bin` (32 bayt, depoya girmez)
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
- [x] Ajan kanalında elle yankı (minicom, `/dev/ttyACM0`, 115200)
- [x] Ajan kanalında yük testi (`tools/echo_test.py`): 102 400 / 102 400 bayt, 0 fark,
      11 422 B/s (hat sınırının %99,1'i). Dairesel tampon ~400 kez başa döndü
- [x] CAN modülü: üzerinde `121` (120 Ω) sonlandırma direnci görüldü. Ek direnç gerekmiyor
- [x] Protokol: 80 test, C↔Python bayt eşitliği dahil

## Derleme ve yükleme

Depo kökünden, CubeIDE penceresini açmadan:

```bash
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

## Açık sorular / kararsız konular

| Konu | Durum | Ne zaman karar verilecek |
|---|---|---|
| LPUART1: BSP üzerinden mi, CubeMX'te çevre birimi olarak mı | ✅ K-017: CubeMX'te çevre birimi, alma DMA ile | — |
| Gazebo: Fortress + TurtleBot 4 mü, mevcut Harmonic'te kendi modelimiz mi | **Açık** (bkz. K-008) | Faz 3 başında |
| LLM model seçimi (araç çağırma şart) | **Açık** | Faz 4 başında |
| Senaryo başına tekrar sayısı | ✅ K-015: LLM senaryolarında 20, arızada 10 | — |

## Bilinen engeller

- **Disk çok dar: 2,8 GB boş (%95).** Faz 3 (Gazebo Fortress + TurtleBot 4, ~2 GB) ve
  Faz 4 (Ollama modeli, ~4 GB) bu hâliyle sığmaz.
  - Kolay aday: `~/STM32Cube/Repository/*.zip` (364 MB). CubeMX'in indirdiği G4 paket
    arşivleri, açılmış hâli ayrıca duruyor.
  - `~/.config/Cursor` + `~/.cursor` (1,85 GB): Cursor kullanıldığı için dokunulmuyor.
  - **Asıl sebep bölüm düzeni:** disk 477 GB ama Ubuntu bölümü (`nvme0n1p5`) 60 GB.
    390 GB BitLocker'lı Windows bölümü, 24 GB ASUS kurtarma bölümü. Kalıcı çözüm
    Windows'tan yer ayırıp Ubuntu'ya yeni bir bölüm eklemek olabilir. **Riskli bir işlem:
    önce yedek alınmalı, BitLocker askıya alınmalı, küçültme Windows'ta yapılmalı.**
    Faz 3'ten önce karar verilecek.
- **NVIDIA sürücüsü kurulu değil.** Kartta RTX 3050 Mobile var (~4 GB VRAM) ama sistem
  Intel iGPU kullanıyor, `nvidia-smi` yok. Faz 4'te yerel LLM için sürücü kurulmalı;
  kurulmazsa model CPU'da çok yavaş kalır ve API'ye geçmek gerekebilir.
- **Gazebo sürüm çakışması.** Sistemde Harmonic (gz-sim8) var; TurtleBot 4'ün Humble
  simülatörü Fortress'e bağımlı. Yan yana kurulabilirler ama `ign`/`gz` komutları ve
  ortam değişkenleri karışabilir.
- **Kablo çekme testi kartı da kapatıyor.** Plan bağlantı kopmasını "kartın USB
  kablosunu çek" diye test ediyor. Ama Nucleo varsayılan olarak o kablodan besleniyor
  (JP5 = 5V_STLK). Kapanan kart kalp atışı kuralını işletemez. **Olası çözüm:** kartı
  E5V girişinden CP2102'nin 5V pininden beslemek. Böylece ajan kanalı kopunca kart araç
  kanalının USB'sinden beslenmeye devam eder. **Faz 2'de UM2505 güç şemasından
  doğrulanacak.**

## Nerede takıldım

(boş)
