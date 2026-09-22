# Claude Code için oturum yönergesi

## Her oturumun başında

1. `docs/STATUS.md` oku — nerede kaldık, sırada ne var, nerede takıldık.
2. `docs/DECISIONS.md` oku — verilmiş kalıcı kararlar. **Bunları yeniden tartışma.**
3. İlgili fazın dosyalarını oku (`docs/RULES.md`, `docs/protocol.md` varsa).

## Her oturumun sonunda

`docs/STATUS.md`'yi güncelle: ne bitti, ne kaldı, nerede takılındı.
Kalıcı bir karar verildiyse `docs/DECISIONS.md`'ye **yeni madde olarak ekle** (silme).

## Proje kuralları

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

## Dil

Proje belgeleri, yorumlar ve commit mesajları Türkçe. Kod tanımlayıcıları İngilizce.
