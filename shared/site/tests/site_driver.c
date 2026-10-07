/* Test sürücüsü: kartın gerçek verisi (site_data.c) ve kuralı (geofence.c)
 * ile her satırdaki "x y" (cm) noktasının kararını yazar (0 OK, 1 izinli
 * alanın dışı, 2 yasak bölge). test_gen_site.py maskeyle karşılaştırır. */
#include <stdio.h>

#include "site/site.h"

int main(void)
{
    int x, y;
    while (scanf("%d %d", &x, &y) == 2) {
        geo_point_t p = { (int16_t)x, (int16_t)y };
        printf("%d\n", (int)geofence_check(&site.fence, p));
    }
    return 0;
}
