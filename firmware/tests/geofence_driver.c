/* Kartın coğrafi sınır kodunu (firmware/app/rules/geofence/) PC'de çalıştıran
 * sürücü. test_geofence.py bunu gcc ile derler, stdin'den komut yollar ve
 * cevabı Python referansıyla karşılaştırır.
 *
 * Her satır bir komut, her komuta bir satır cevap. Sayılar ondalık.
 *   allowed <n> <x1> <y1> ... <xn> <yn>    → izinli çokgeni kurar, yasakları
 *                                           siler; "ok"
 *   forbidden <n> <x1> <y1> ... <xn> <yn>  → bir yasak çokgen ekler; "ok"
 *   check <x> <y>                          → OK, OUT ya da FORBID
 *
 * Sınır sayıları burada denetlenmez: n ve yasak çokgen sayısı geofence_t'nin
 * sınırlarını aşarsa yine yazılır (dizi boyutu kadar köşeyle). geofence_check
 * geçersiz sınırı reddetmeli, bu da sınanır. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "rules/geofence/geofence.h"

#define LINE_MAX_CHARS 4096

static geofence_t fence;

/* "n x1 y1 ..." okur. En fazla cap köşeyi v'ye yazar, n'yi olduğu gibi
 * döndürür (geçersiz sınır sınansın diye). Hatada -1. */
static int read_polygon(char **rest, geo_point_t *v, unsigned cap)
{
    char *end;
    long n = strtol(*rest, &end, 10);
    if (end == *rest || n < 0 || n > 255) {
        return -1;
    }
    *rest = end;
    for (long i = 0; i < n; i++) {
        long x = strtol(*rest, &end, 10);
        long y = strtol(end, rest, 10);
        if (x < INT16_MIN || x > INT16_MAX || y < INT16_MIN || y > INT16_MAX) {
            return -1;
        }
        if ((unsigned long)i < cap) {
            v[i].x_cm = (int16_t)x;
            v[i].y_cm = (int16_t)y;
        }
    }
    return (int)n;
}

int main(void)
{
    static char line[LINE_MAX_CHARS];
    while (fgets(line, sizeof line, stdin) != NULL) {
        char *rest = line;
        if (strncmp(line, "allowed ", 8) == 0) {
            rest += 8;
            memset(&fence, 0, sizeof fence);
            int n = read_polygon(&rest, fence.allowed.v, GEOFENCE_ALLOWED_MAX);
            fence.allowed.n = (uint8_t)n;
            puts(n < 0 ? "ERR" : "ok");
        } else if (strncmp(line, "forbidden ", 10) == 0) {
            rest += 10;
            unsigned k = fence.n_forbidden;
            geo_forbidden_t scratch;
            geo_forbidden_t *f = k < GEOFENCE_FORBIDDEN_MAX ? &fence.forbidden[k] : &scratch;
            int n = read_polygon(&rest, f->v, GEOFENCE_FORBIDDEN_VERTICES_MAX);
            f->n = (uint8_t)n;
            fence.n_forbidden = (uint8_t)(k + 1u);
            puts(n < 0 ? "ERR" : "ok");
        } else if (strncmp(line, "check ", 6) == 0) {
            long x = strtol(line + 6, &rest, 10);
            long y = strtol(rest, NULL, 10);
            geo_point_t p = { (int16_t)x, (int16_t)y };
            switch (geofence_check(&fence, p)) {
            case GEOFENCE_OK:              puts("OK");     break;
            case GEOFENCE_OUTSIDE_ALLOWED: puts("OUT");    break;
            case GEOFENCE_IN_FORBIDDEN:    puts("FORBID"); break;
            }
        } else {
            puts("ERR");
        }
        fflush(stdout);
    }
    return 0;
}
