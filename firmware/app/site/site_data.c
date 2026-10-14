/* OTOMATİK ÜRETİLDİ. ELLE DÜZENLEMEYİN.
 * Kaynak: shared/site/ika_saha.yaml
 * Üretici: tools/gen_site.py
 *
 * Koordinatlar cm, harita çerçevesi. Güvenlik payı 1 m uygulandı
 * (K-036): izinli alan içeri çekildi, yasak bölgeler büyütüldü. */
#include "site/site.h"

const site_t site = {
    .fence = {
        .allowed = {
            .n = 4,
            .v = { {-159, -859}, {2759, -859}, {2759, 859}, {-159, 859} },
        },
        .n_forbidden = 3,
        .forbidden = {
            { .n = 4, .v = { {200, -920}, {1000, -920}, {1000, -350}, {200, -350} } },   /* personel */
            { .n = 4, .v = { {1200, -250}, {1700, -250}, {1700, 250}, {1200, 250} } },   /* kazi */
            { .n = 4, .v = { {1600, -920}, {2400, -920}, {2400, -350}, {1600, -350} } },   /* yakit */
        },
    },
    .home = {0, 0},
    .n_safe = 5,
    .safe = {
        {0, 0},   /* baslangic */
        {175, 600},   /* kuzeybati */
        {850, 100},   /* konteyner_onu */
        {2600, 0},   /* kapi_onu */
        {1300, -550},   /* guney */
    },
};
