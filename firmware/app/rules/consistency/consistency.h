/* Tutarlılık (docs/RULES.md §3.4, K-049).
 *
 * Görev komutu ajanın varsaydığı araç konumunu (inanç) ve onu okuduğu anı
 * taşır. Kart bunu son telemetriyle kıyaslar:
 *     tol(Δt) = d₀ + v_max × Δt,   d₀ = 25 cm,   v_max = LIMIT_V_MAX_MM_S
 *     Δt = şimdi − inancın okunduğu an,   −50 ms ≤ Δt ≤ 5 s
 * Araç Δt sürede bekçinin hız sınırından hızlı gidemez: tolerans fiziksel bir
 * üst sınırdan türetilir. Kaba hataları yakalar (yanlış çerçeve, x/y yer
 * değiştirmiş, uydurulmuş konum). Telemetri 500 ms'den eskiyse denetlenemez:
 * ret. Yalnız konum, yön değil.
 *
 * Hesap tamsayıyla (cm, ms); uzaklık karesiyle kıyaslanır, VERDICT için
 * tamsayı karekök. Donanıma dokunmaz, PC'de sınanır (firmware/tests/). */
#ifndef CONSISTENCY_H
#define CONSISTENCY_H

#include <stdint.h>

#include "rules/geofence/geofence.h"

#define CONSISTENCY_D0_CM                  25
#define CONSISTENCY_MAX_BELIEF_AGE_MS    5000   /* K-049: 5 s'de tolerans 3,25 m */
#define CONSISTENCY_TELEMETRY_MAX_AGE_MS  500   /* kalp atışıyla aynı eşik */

typedef enum {
    CONSISTENCY_OK = 0,
    CONSISTENCY_TOO_FAR,              /* value fark (cm), hi tolerans (cm) */
    CONSISTENCY_BELIEF_TOO_OLD,       /* value Δt (ms), hi 5000 */
    CONSISTENCY_BELIEF_FROM_FUTURE,   /* value Δt (ms, negatif), lo −50 */
    CONSISTENCY_NO_TELEMETRY,         /* value telemetri yaşı (ms), hi 500 */
} consistency_result_t;

typedef struct {
    int32_t value;
    int32_t lo;
    int32_t hi;
} consistency_detail_t;

consistency_result_t consistency_check(uint32_t now_ms, geo_point_t belief, uint32_t belief_ts_ms,
                                       geo_point_t telemetry, uint32_t telemetry_age_ms,
                                       consistency_detail_t *d);

#endif /* CONSISTENCY_H */
