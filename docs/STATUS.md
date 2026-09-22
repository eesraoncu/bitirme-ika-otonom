# Proje Durumu

> Bu dosya her çalışma oturumunun **başında okunur**, **sonunda güncellenir**.
> Claude Code ile çalışırken ilk iş: bu dosyayı ve `docs/DECISIONS.md`'yi okut.

**Son güncelleme:** 2026-09-22
**Bulunduğumuz faz:** Faz 0 — Kurulum

---

## Şu an ne yapılıyor

Faz 0 (kurulum) tamamlanıyor. Proje iskeleti kuruldu, eksik araçların kurulumu sürüyor.

## Bitenler

- [x] Disk temizliği: 4.3 GB → 11 GB boş alan
- [x] Proje klasör yapısı kuruldu (`docs/`, `shared/`, `firmware/`, `ros2_ws/`, `analysis/`)
- [x] Ubuntu 22.04.5 LTS
- [x] ROS 2 Humble (önceden kuruluydu)
- [x] Nav2 (30 paket, önceden kuruluydu)
- [x] `teleop_twist_keyboard` (önceden kuruluydu)
- [x] Git, VS Code, Claude Code

## Sırada (Faz 0 kalanı)

- [ ] `dialout` grubuna ekleme — seri porta şifresiz erişim için (oturum kapatıp açmak gerekir)
- [ ] `minicom`, `python3-serial`, `pulseview`, `sigrok-firmware-fx2lafw`
- [ ] RTAB-Map (`ros-humble-rtabmap-ros`)
- [ ] STM32CubeIDE — st.com'dan elle indirilecek (myST hesabı gerekir)
- [ ] Ollama — kurulacak, model seçimi Faz 4'e bırakıldı
- [ ] GitHub'da `bitirme-ika-bekci` özel deposu açıp bağlamak
- [ ] Parça siparişi: 2× SN65HVD230, 1× USB-TTL, 1× mantık analizörü, jumper, breadboard

## Açık sorular / kararsız konular

| Konu | Durum | Ne zaman karar verilecek |
|---|---|---|
| Gazebo: Fortress + TurtleBot 4 mü, mevcut Harmonic'te kendi modelimiz mi | **Açık** | Faz 3 başında |
| LLM model seçimi (araç çağırma şart) | **Açık** | Faz 4 başında |
| Senaryo başına tekrar sayısı (plan 20 öneriyor) | **Açık** | Faz 1'de hocayla |

## Bilinen engeller

- **NVIDIA sürücüsü kurulu değil.** Kartta RTX 3050 Mobile var (~4 GB VRAM) ama sistem Intel iGPU kullanıyor, `nvidia-smi` yok. Faz 4'te yerel LLM çalıştırmak için sürücü kurulmalı; kurulmazsa model CPU'da çok yavaş kalır ve API'ye geçmek gerekebilir.
- **Gazebo sürüm çakışması.** Sistemde Harmonic (gz-sim8) var; TurtleBot 4'ün Humble simülatörü Fortress'e bağımlı. Yan yana kurulabilirler ama `ign`/`gz` komutları ve ortam değişkenleri karışabilir.
- **Disk.** 11 GB boş. STM32CubeIDE (~2.5 GB) + Fortress/TurtleBot4 (~2 GB) + Ollama modeli (~4 GB) sonrası rahatlık payı azalacak.

## Nerede takıldım

(boş)
