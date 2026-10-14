/* Tazelik (docs/RULES.md §3.3, docs/protocol.md §6.4).
 *
 * Komut yaşı = kartın şimdiki zamanı − komutun zaman damgası (ts_ms, kartın
 * saat alanında: köprü kalp atışlarıyla eşitler, protocol §6.2). Kabul aralığı
 * −50 ms ≤ yaş ≤ 200 ms. Alt sınır eşitleme hatasına tanınan pay: daha ileriden
 * gelen damga eşitlemenin bozulduğunu gösterir.
 *
 * Saat 49 günde taşar: fark işaretli 32 bit olarak yorumlanır, taşma sınırında
 * da doğru. Donanıma dokunmaz, PC'de sınanır (firmware/tests/). */
#ifndef FRESHNESS_H
#define FRESHNESS_H

#include <stdint.h>

#define FRESHNESS_MAX_AGE_MS     200
#define FRESHNESS_MAX_FUTURE_MS   50

typedef enum {
    FRESHNESS_OK = 0,
    FRESHNESS_TOO_OLD,       /* VERDICT'te TOO_OLD */
    FRESHNESS_FROM_FUTURE,   /* VERDICT'te FROM_FUTURE */
} freshness_result_t;

/* now − ts, işaretli (ms): ileriden gelen damgada negatif. Saat taşmasında
 * doğru. Tutarlılık kuralı da kullanır (inancın yaşı). */
int32_t time_age_ms(uint32_t now_ms, uint32_t ts_ms);

/* *age_ms: yaş (ms), ileriden gelen damgada negatif. */
freshness_result_t freshness_check(uint32_t now_ms, uint32_t ts_ms, int32_t *age_ms);

#endif /* FRESHNESS_H */
