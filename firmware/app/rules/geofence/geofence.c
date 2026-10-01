#include "rules/geofence/geofence.h"

#include <stdbool.h>
#include <stddef.h>

typedef enum {
    POLY_OUTSIDE,
    POLY_BOUNDARY,
    POLY_INSIDE,
} poly_pos_t;

/* (b − a) × (p − a): p, a'dan b'ye giden kenarın solundaysa pozitif,
 * sağındaysa negatif, aynı doğrudaysa 0. Koordinat farkları ±65 535'e,
 * iki çarpımın farkı ±2 × 65 535² ≈ ±8,6 milyara çıkar: 32 bit taşar,
 * 64 bitle hesaplanır. */
static int64_t cross(geo_point_t a, geo_point_t b, geo_point_t p)
{
    int64_t abx = (int64_t)b.x_cm - a.x_cm;
    int64_t aby = (int64_t)b.y_cm - a.y_cm;
    int64_t apx = (int64_t)p.x_cm - a.x_cm;
    int64_t apy = (int64_t)p.y_cm - a.y_cm;
    return abx * apy - aby * apx;
}

static bool between(int16_t v, int16_t a, int16_t b)
{
    return a <= b ? (a <= v && v <= b) : (b <= v && v <= a);
}

static bool on_segment(geo_point_t a, geo_point_t b, geo_point_t p)
{
    return cross(a, b, p) == 0 &&
           between(p.x_cm, a.x_cm, b.x_cm) && between(p.y_cm, a.y_cm, b.y_cm);
}

/* Işın atma: p'den sağa (+x) giden ışının kaç kenarı kestiği sayılır. Tek
 * sayı içeride demektir.
 *
 * Yarı açık kural: kenar ancak p'nin yüksekliğini alt ucu dahil, üst ucu
 * hariç kapsıyorsa sayılır. Işın bir köşeden geçerse o köşe iki kenardan
 * yalnızca birinde sayılır; yatay kenarlar hiç sayılmaz.
 *
 * Kesişimin p'nin sağında olup olmadığı bölme yapmadan, çapraz çarpımın
 * işaretinden bulunur: yukarı giden kenar için p kenarın solundaysa (> 0),
 * aşağı giden kenar için sağındaysa (< 0) ışın kenarı keser. */
static poly_pos_t locate(const geo_point_t *v, size_t n, geo_point_t p)
{
    bool inside = false;
    for (size_t i = 0, j = n - 1u; i < n; j = i++) {
        geo_point_t a = v[j];
        geo_point_t b = v[i];
        if (on_segment(a, b, p)) {
            return POLY_BOUNDARY;
        }
        if ((a.y_cm > p.y_cm) != (b.y_cm > p.y_cm)) {
            bool upward = b.y_cm > a.y_cm;
            if ((cross(a, b, p) > 0) == upward) {
                inside = !inside;
            }
        }
    }
    return inside ? POLY_INSIDE : POLY_OUTSIDE;
}

static bool valid(const geofence_t *g)
{
    if (g->allowed.n < 3u || g->allowed.n > GEOFENCE_ALLOWED_MAX ||
        g->n_forbidden > GEOFENCE_FORBIDDEN_MAX) {
        return false;
    }
    for (size_t k = 0; k < g->n_forbidden; k++) {
        if (g->forbidden[k].n < 3u || g->forbidden[k].n > GEOFENCE_FORBIDDEN_VERTICES_MAX) {
            return false;
        }
    }
    return true;
}

geofence_result_t geofence_check(const geofence_t *g, geo_point_t p)
{
    if (!valid(g) || locate(g->allowed.v, g->allowed.n, p) != POLY_INSIDE) {
        return GEOFENCE_OUTSIDE_ALLOWED;
    }
    for (size_t k = 0; k < g->n_forbidden; k++) {
        if (locate(g->forbidden[k].v, g->forbidden[k].n, p) != POLY_OUTSIDE) {
            return GEOFENCE_IN_FORBIDDEN;
        }
    }
    return GEOFENCE_OK;
}
