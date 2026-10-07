/* Test sürücüsü: kartın gerçek verisi (site_data.c) ve kodu (geofence.c, site.c).
 * Her satır bir soru, cm cinsinden:
 *   g x y  → geofence_check kararı (0 OK, 1 izinli alanın dışı, 2 yasak bölge)
 *   n x y  → site_nearest_safe cevabı "x y"
 * test_gen_site.py cevapları maskeyle ve üretecin Python eşiyle karşılaştırır. */
#include <stdio.h>

#include "site/site.h"

int main(void)
{
    char c;
    int x, y;
    while (scanf(" %c %d %d", &c, &x, &y) == 3) {
        geo_point_t p = { (int16_t)x, (int16_t)y };
        if (c == 'g') {
            printf("%d\n", (int)geofence_check(&site.fence, p));
        } else if (c == 'n') {
            geo_point_t s = site_nearest_safe(&site, p);
            printf("%d %d\n", s.x_cm, s.y_cm);
        } else {
            return 2;
        }
    }
    return 0;
}
