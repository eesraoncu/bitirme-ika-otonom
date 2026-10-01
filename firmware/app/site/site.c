#include "site/site.h"

#include <stddef.h>

/* Kare uzaklık: karekök gerekmez, sıralama aynı kalır. Farklar ±65 535,
 * kareleri toplamı ~8,6 milyar: 64 bit. */
static int64_t dist2(geo_point_t a, geo_point_t b)
{
    int64_t dx = (int64_t)a.x_cm - b.x_cm;
    int64_t dy = (int64_t)a.y_cm - b.y_cm;
    return dx * dx + dy * dy;
}

geo_point_t site_nearest_safe(const site_t *s, geo_point_t p)
{
    size_t n = s->n_safe < SITE_SAFE_POINTS_MAX ? s->n_safe : SITE_SAFE_POINTS_MAX;
    if (n == 0u) {
        return s->home;
    }
    size_t best = 0;
    for (size_t i = 1; i < n; i++) {
        if (dist2(s->safe[i], p) < dist2(s->safe[best], p)) {   /* eşitlikte ilki kalır */
            best = i;
        }
    }
    return s->safe[best];
}
