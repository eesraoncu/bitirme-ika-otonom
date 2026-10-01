/* Harita verisi: coğrafi sınır, başlangıç noktası ve güvenli noktalar
 * (docs/RULES.md §3.1, §5.3).
 *
 * Derleme zamanında karta gömülür, protokolle gönderilmez: güvenilmeyen
 * tarafın bunları değiştirebilmesi denetimin anlamını ortadan kaldırırdı
 * (docs/protocol.md §2). Faz 3'te tek bir harita dosyasından üretilecek;
 * sınır ve noktalar o yüzden aynı yerde. Kartın verisi site_data.c'de. */
#ifndef SITE_H
#define SITE_H

#include <stdint.h>

#include "rules/geofence/geofence.h"

#define SITE_SAFE_POINTS_MAX 8u

typedef struct {
    geofence_t fence;
    geo_point_t home;                          /* başlangıç noktası */
    uint8_t n_safe;
    geo_point_t safe[SITE_SAFE_POINTS_MAX];    /* kayıtlı güvenli noktalar */
} site_t;

/* Kartın harita verisi (site_data.c). */
extern const site_t site;

/* p'ye düz çizgi (Öklid) uzaklığı en küçük güvenli nokta. Eşitlikte sıra
 * numarası küçük olan (RULES §5.3). Güvenli nokta yoksa başlangıç noktası. */
geo_point_t site_nearest_safe(const site_t *s, geo_point_t p);

#endif /* SITE_H */
