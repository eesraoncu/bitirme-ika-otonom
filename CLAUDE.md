# Claude Code için oturum yönergesi

## Her oturumun başında

1. `docs/STATUS.md` oku — nerede kaldık, sırada ne var, nerede takıldık.
2. `docs/DECISIONS.md` oku — verilmiş kalıcı kararlar. **Bunları yeniden tartışma.**
3. İlgili fazın dosyalarını oku (`docs/RULES.md`, `docs/protocol.md` varsa).

## Her oturumun sonunda

`docs/STATUS.md`'yi güncelle: ne bitti, ne kaldı, nerede takılındı.
Kalıcı bir karar verildiyse `docs/DECISIONS.md`'ye **yeni madde olarak ekle** (silme).

## Proje kuralları

- **Önce anlat, onay al, sonra yaz.** Esra'nın haberi ve onayı olmadan tek satır kod
  yazılmaz, hiçbir dosya (belgeler dahil) değiştirilmez. Sıra: ne yazılacak, neden
  gerekli, nasıl çalışacak → Esra onaylar → yazılır → nasıl çalıştırılacağı gösterilir.
  Sebep: projenin asıl amacı Esra'nın öğrenmesi. (Esra'nın kararı, 2026-09-26.)
- **Mesaj formatı tek yerde.** `shared/protocol/messages.yaml` dışında hiçbir yerde
  mesaj alanı elle tanımlanmaz. C başlığı ve Python modülü buradan üretilir.
- **Bir kavram tek klasörde.** Bir kuralı değiştirmek tek klasöre bakmayı gerektirmeli.
  Bir değişiklik birden fazla klasöre dokunuyorsa tasarım yanlıştır, önce onu söyle.
- **CubeMX'in ürettiği dosyalara kod yazılmaz.** Tüm proje kodu `firmware/app/` altında;
  üretilen dosyalara yalnızca bu klasördeki fonksiyonları çağıran birkaç satır eklenir.
  Sebep: CubeMX ayarı yeniden üretildiğinde kod silinmesin.
- **Sırlar depoya girmez.** HMAC anahtarı `secrets/` altında ve `.gitignore`'da.
- **Kapsam kuralı.** Yeni bir özellik ancak sonuç tablosuna yeni bir satır ekliyorsa
  eklenir. Fazladan özellik önerme.
- **Karta yükleme yapmadan önce onay al.** Flash'a yazma, silme, option byte değiştirme,
  ST-LINK üzerinden reset: hiçbiri Esra'nın açık onayı olmadan yapılmaz. Derlemek ve
  karttan salt okuma (ör. `STM32_Programmer_CLI -c port=SWD` ile kimlik okumak) serbest.
- **Commit'lerde yalnızca Esra'nın adı.** Commit mesajlarına `Co-Authored-By` ya da
  başka bir atıf satırı eklenmez, PR açıklamalarına "Generated with ..." satırı konmaz.
  Yazar ve commit eden: `Esra Öncü <eesraoncu@icloud.com>`. (Esra'nın kararı, 2026-09-24.
  Geçmişteki bütün commit'lerden de temizlendi.)

## Dil

Proje belgeleri, yorumlar ve commit mesajları Türkçe. Kod tanımlayıcıları İngilizce.
