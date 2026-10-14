/* Fiziksel limitler (docs/RULES.md §1, §3.2, K-046).
 *
 * Hız komutu (Nav2, 20 Hz) reddedilmez, kırpılır: önce ivme, sonra hız. İvme
 * yalnız hızlanmada kırpılır: aynı işaret ve büyüyen büyüklük. Yavaşlama, durma
 * ve işaret değişimi serbest (Nav2'nin velocity_smoother'ıyla aynı tanım).
 * Görev komutu (hiz_siniri) kırpılmaz, aralık dışındaysa reddedilir.
 *
 * Birimler protokoldeki gibi mm/s ve mrad/s: hesap tamsayıyla, yuvarlama yok.
 * Donanıma dokunmaz, PC'de sınanır (firmware/tests/). */
#ifndef LIMITS_H
#define LIMITS_H

#include <stdint.h>

#define LIMIT_V_MAX_MM_S    600   /* ±0,6 m/s: Nav2'nin 0,5'inin 1,2 katı */
#define LIMIT_W_MAX_MRAD_S  600   /* ±0,6 rad/s */
/* Komut başına en çok hızlanma, sabit T = 50 ms ile (Nav2 20 Hz, §3.2):
 * 0,6 m/s² × 0,05 s = 30 mm/s · 1,2 rad/s² × 0,05 s = 60 mrad/s. */
#define LIMIT_DV_MM_S        30
#define LIMIT_DW_MRAD_S      60

/* Bir eksenin (doğrusal ya da açısal) kırpılmış değeri. prev: araca son
 * GÖNDERİLEN değer (§3.2). Hızlanmada prev ± step içine, sonra ±max içine. */
int16_t limit_axis(int16_t cmd, int16_t prev, int16_t step, int16_t max);

typedef enum {
    LIMIT_OK = 0,
    LIMIT_NOT_POSITIVE,   /* VERDICT'te NOT_POSITIVE */
    LIMIT_ABOVE_MAX,      /* VERDICT'te ABOVE_MAX */
} limit_result_t;

/* hiz_siniri (SPEED_LIMIT_CMD): 0 < değer ≤ LIMIT_V_MAX_MM_S. */
limit_result_t limit_speed_cmd(uint16_t limit_mm_s);

#endif /* LIMITS_H */
