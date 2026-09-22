# Proje Durumu

> Bu dosya her çalışma oturumunun **başında okunur**, **sonunda güncellenir**.
> Claude Code ile çalışırken ilk iş: bu dosyayı ve `docs/DECISIONS.md`'yi okut.

**Son güncelleme:** 2026-09-22
**Bulunduğumuz faz:** Faz 0 — Kurulum (neredeyse bitti)

---

## Şu an ne yapılıyor

Faz 0 tamamlandı sayılır. Kalan tek yazılım kalemi Ollama; o da model seçimi
Faz 4'e bırakıldığı için acil değil. Sırada **Faz 1** var.

## Bitenler

- [x] Disk temizliği: 4.3 GB → 11 GB (kurulumlar sonrası 6.4 GB boş)
- [x] Proje klasör yapısı + git deposu + ilk commit
- [x] Ubuntu 22.04.5 LTS · ROS 2 Humble · Nav2 (30 paket) · teleop_twist_keyboard
- [x] Git, VS Code, Claude Code
- [x] `minicom`, `python3-serial`, `pulseview`, `sigrok-firmware-fx2lafw`, `unzip`
- [x] RTAB-Map (`ros-humble-rtabmap-ros`, 14 paket)
- [x] STM32CubeIDE 2.2.0 → `/opt/st/stm32cubeide_2.2.0`
- [x] ST-LINK udev kuralları kuruldu (49-stlinkv1/v2/v2-1/v3.rules)
- [x] `dialout` grubuna eklendi (sistem kaydında var)
- [x] GitHub'da `bitirme-ika-otonom` özel deposu açıldı

## Sırada

- [ ] **Oturumu kapatıp aç** — `dialout` üyeliği ancak o zaman geçerli olur
- [ ] Ollama kurulumu (model seçimi Faz 4'te)
- [ ] Parça siparişi (~511 TL, bkz. `docs/malzeme-listesi.md`): 2× SN65HVD230
      (3,3 V), CP2102 USB-TTL (6 pinli), M-F + F-F jumper, breadboard, 2× 120 Ω
      — artı **micro-USB data kablosu** (en öncelikli kalem)
      — **mantık analizörü ertelendi, bkz. K-009**
- [ ] **Faz 1 başlangıcı:** `docs/RULES.md` eşik değerleri, `docs/protocol.md`
      mesaj çerçevesi, `shared/protocol/messages.yaml` + kod üreticisi

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
| Senaryo başına tekrar sayısı (plan 20 öneriyor) | **Açık** | Faz 1'de hocayla |

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

## Nerede takıldım

(boş)
