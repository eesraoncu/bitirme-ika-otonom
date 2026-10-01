/* DENEME VERİSİ. Gerçek koordinatlar Faz 3'te haritadan üretilecek
 * (docs/RULES.md §7). O zamana kadar bu değerler yalnızca kartın kararlarını
 * sınamak içindir: 20 m × 20 m izinli alan, içinde 2 m × 2 m yasak bölge,
 * üç güvenli nokta. tools/decision_test.py aynı değerleri kullanır. */
#include "site/site.h"

const site_t site = {
    .fence = {
        .allowed = {
            .n = 4,
            .v = { {-1000, -1000}, {1000, -1000}, {1000, 1000}, {-1000, 1000} },
        },
        .n_forbidden = 1,
        .forbidden = {
            { .n = 4, .v = { {300, 300}, {500, 300}, {500, 500}, {300, 500} } },
        },
    },
    .home = {0, 0},
    .n_safe = 3,
    .safe = { {-700, -700}, {700, -700}, {-700, 700} },
};
