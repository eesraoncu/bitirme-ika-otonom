# Proje Durumu

> Bu dosya her çalışma oturumunun **başında okunur**, **sonunda güncellenir**.
> Claude Code ile çalışırken ilk iş: bu dosyayı ve `docs/DECISIONS.md`'yi okut.

**Son güncelleme:** 2026-09-24
**Bulunduğumuz faz:** Faz 1 tamamlandı → sırada Faz 2 (STM32 tarafı)

---

## Şu an ne yapılıyor

**Faz 1 bitti.** Planın koşulu sağlandı: `docs/RULES.md` ve `docs/protocol.md` tamam,
`messages.yaml`'dan C başlığı ve Python modülü üretilebiliyor. Üretilen C ile Python'un
aynı baytları ürettiği testle kanıtlandı (80 test, `python3 -m pytest shared/protocol/tests`).
Tekrar sayısı da kararlaştırıldı (K-015).

**Faz 2'nin kartsız yapılabilecek kısmı** (kablo gelmeden başlanabilir):
- CubeMX projesi ve 170 MHz saat ayarı (HSE ile, `protocol.md` §6.1). Derleme kartsız yapılır.
- C çerçeveleyici (COBS, CRC-16, HMAC-SHA256). Bilgisayarda gcc ile
  `test_vectors.json`'a karşı test edilebilir. Karta yüklemeden önce doğrulanmış olur.

## Bitenler

- [x] Disk temizliği: 4.3 GB → 11 GB (kurulumlar sonrası 6.4 GB boş)
- [x] Proje klasör yapısı + git deposu + ilk commit
- [x] Ubuntu 22.04.5 LTS · ROS 2 Humble · Nav2 (30 paket) · teleop_twist_keyboard
- [x] Git, VS Code, Claude Code
- [x] `minicom`, `python3-serial`, `pulseview`, `sigrok-firmware-fx2lafw`, `unzip`
- [x] RTAB-Map (`ros-humble-rtabmap-ros`, 14 paket)
- [x] STM32CubeIDE 2.2.0 → `/opt/st/stm32cubeide_2.2.0`
- [x] ST-LINK udev kuralları kuruldu (49-stlinkv1/v2/v2-1/v3.rules)
- [x] `dialout` grubuna eklendi ve oturumda doğrulandı (2026-09-24)
- [x] GitHub'da `bitirme-ika-otonom` özel deposu açıldı
- [x] **Faz 1:** okuma listesi tamamlandı
- [x] **Faz 1:** `docs/RULES.md`: katmanlı hız limitleri, eşikler, denetim sırası,
      kurtarma durum makinesi. Tüm değerler onaylandı (K-010 … K-013)
- [x] **Faz 1:** `docs/protocol.md`: tehdit modeli, çerçeve (COBS + CRC + HMAC), oturum,
      zaman eşitleme, VERDICT biçimi, CAN eşlemesi (K-014)
- [x] **Faz 1:** `shared/protocol/messages.yaml` (17 mesaj), `tools/gen_protocol.py`,
      referans çerçeveleyici `frame.py`, `test_vectors.json`, 80 test

## Sırada

- [ ] Ollama kurulumu (model seçimi Faz 4'te)
- [x] **Parça siparişi geldi (2026-09-24).** Robiz.net'ten tek sipariş, 656,16 TL — tam liste ve
      gerekçeleri `docs/malzeme-listesi.md`'de. 2× SN65HVD230, CP2102 USB-TTL,
      micro-USB **data** kablosu, M-F + F-F + M-M jumper, MB-102 breadboard.
      Hepsi stokta doğrulandı (2026-09-22).
      — 120 Ω direnç siparişe dahil değil: modüller gelince üzerinde var mı bakılacak
      — mantık analizörü ertelendi (K-009)
- [ ] **Faz 2.1:** CubeMX projesi (`firmware/`), 170 MHz, **HSE** saat kaynağı
- [ ] **Faz 2.6'nın kartsız kısmı:** `firmware/app/protocol/` altında C çerçeveleyici.
      `test_vectors.json`'a karşı gcc ile test. Etiket sabit zamanlı karşılaştırılmalı
- [ ] HMAC anahtarını üret: `secrets/hmac_key.bin` (32 bayt, depoya girmez)

## Doğrulanmış testler

- [x] CubeIDE kuruldu
- [x] Kart kimliği doğrulandı: **NUCLEO-G474RE, MB1367/C**, CN1 = **micro-USB**
- [ ] **LED testi (plan 3.6) yapılamadı — veri kablosu yok.** Eldeki JBL
      hoparlör kablosu denendi: karta besleme gidiyor (LD3 yanıyor) ama
      `lsusb`'de ST cihazı yok → kabloda veri teli yok. Micro-USB **data**
      kablosu sipariş listesine eklendi, en öncelikli kalem.

## Açık sorular / kararsız konular

| Konu | Durum | Ne zaman karar verilecek |
|---|---|---|
| Gazebo: Fortress + TurtleBot 4 mü, mevcut Harmonic'te kendi modelimiz mi | **Açık** (bkz. K-008) | Faz 3 başında |
| LLM model seçimi (araç çağırma şart) | **Açık** | Faz 4 başında |
| Senaryo başına tekrar sayısı | ✅ K-015: LLM senaryolarında 20, arızada 10 | — |

## Bilinen engeller

- **Disk dar: 6.4 GB boş.** Gazebo Fortress + TurtleBot 4 (~2 GB) ve Ollama modeli
  (~4 GB) ikisi birden sığmaz. Faz 3 ve Faz 4'ten önce yeniden yer açmak gerekecek.
  Adaylar: `~/.config/Cursor` + `~/.cursor` (1.85 GB), `~/.antigravity-ide` (141 MB),
  `~/.cache/ms-playwright-go` (128 MB).
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
