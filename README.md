# LLM Komutan, Gömülü Bekçi

Doğal dille görev alan otonom İKA için bağımsız, gerçek zamanlı gömülü komut denetleyicisi.

**Esra Öncü** · Bitirme Projesi · 2026–2027

## Tek cümlede

Simülasyondaki bir insansız kara aracı vSLAM ile ortamın haritasını çıkarır ve doğal
dille verilen görevleri bu harita üzerinde yerine getirir. Görevi komutlara çeviren LLM
ajanının ürettiği her komut, araca ulaşmadan önce ondan bağımsız çalışan bir STM32
kartından geçer. Kart güvenli olmayan komutu reddeder, gerekçesini ajana bildirir ve
gerekirse aracı kendi başına güvenli duruma alır.

## Araştırma soruları

- **S1** Bağımsız gömülü bekçi, LLM'in ürettiği güvensiz komutların ne kadarını ne kadar
  sürede yakalıyor; geçerli komutların ne kadarını haksız yere reddediyor?
- **S2** Aynı hatalara karşı bağımsız bekçi, navigasyon yığınının yerleşik korumalarına
  (Nav2 yasak bölge filtresi ve çarpışma izleyici) göre ne fark yaratıyor?
- **S3** Ret gerekçesinin ajana geri verilmesi, görevin güvenli şekilde tamamlanma
  oranını ve süresini nasıl etkiliyor?

## Klasörler

| Klasör | İçerik |
|---|---|
| `docs/` | STATUS (her oturum), DECISIONS (kalıcı kararlar), RULES (eşik değerleri), protocol (mesaj çerçevesi) |
| `shared/protocol/` | `messages.yaml` — mesajların **tek** tanımı; C ve Python buradan üretilir |
| `firmware/` | STM32CubeIDE projesi; tüm proje kodu `firmware/app/` altında |
| `ros2_ws/src/` | `ika_sim`, `ika_nav`, `guard_bridge`, `llm_agent`, `experiments` |
| `analysis/` | Sonuç betikleri ve grafikler |
| `tools/` | Kod üreticisi ve yardımcı betikler |

## Donanım

STM32 NUCLEO-G474RE · 2× SN65HVD230 CAN alıcı-verici · USB-TTL dönüştürücü ·
8 kanal mantık analizörü

Üç fiziksel hat: **ajan kanalı** (PC USB → Nucleo VCP), **CAN hattı**
(FDCAN1 → modül → tel → modül → FDCAN2), **araç kanalı** (USART → USB-TTL → PC USB).

## Çalışma düzeni

1. Her oturum `docs/STATUS.md` okunarak başlar, güncellenerek biter.
2. Kalıcı kararlar `docs/DECISIONS.md`'ye yalnızca eklenir.
3. Küçük adımlarla ve anlamlı mesajlarla commit edilir; çalışan her ara durum kaydedilir.
4. **Kapsam kuralı:** yeni bir özellik ancak sonuç tablosuna yeni bir satır ekliyorsa eklenir.
