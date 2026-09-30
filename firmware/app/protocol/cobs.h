/* COBS: veriyi içinde hiç 0x00 kalmayacak şekilde yeniden yazar. Böylece
 * hatta 0x00 yalnızca çerçeve sonunda görünür ve alıcı bir bozulmadan sonra
 * bir sonraki 0x00'da senkronu geri bulur (docs/protocol.md §4.2).
 *
 * Her 0x00'ın yerine "bir sonraki sıfıra kaç adım var" yazılır:
 *   11 22 00 33  →  03 11 22 02 33
 * Kanonik biçim: veri tam 254 sıfırsız baytlık bir blokla biterse sona ek
 * kod baytı konmaz. Python'daki frame.py ile aynı. */
#ifndef COBS_H
#define COBS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* len baytlık verinin kodlanmış hâlinin en büyük boyu. Her 254 baytta en
 * fazla bir kod baytı eklenir. Ayraç (0x00) buna dahil değil. */
#define COBS_ENCODED_MAX(len) ((len) + (len) / 254u + 1u)

/* in'deki len baytı kodlayıp out'a yazar, yazılan bayt sayısını döndürür.
 * out en az COBS_ENCODED_MAX(len) bayt olmalı. Ayracı eklemez. */
size_t cobs_encode(const uint8_t *in, size_t len, uint8_t *out);

/* Ayraçsız kodlanmış in'i çözüp out'a yazar. Başarılıysa true döner ve
 * çözülen bayt sayısını *out_len'e yazar. Boş girdide, içinde 0x00 varsa,
 * bir kod girdinin sonunun ötesini gösteriyorsa ya da sonuç out_max'a
 * sığmıyorsa false döner (STATUS.err_framing). */
bool cobs_decode(const uint8_t *in, size_t len, uint8_t *out, size_t out_max,
                 size_t *out_len);

#endif /* COBS_H */
