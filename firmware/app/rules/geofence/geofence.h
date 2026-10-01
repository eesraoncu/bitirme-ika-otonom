/* Coğrafi sınır (docs/RULES.md §3.1).
 *
 * Bir izinli çokgen (dış sınır) ve en fazla 4 yasak çokgen (iç delikler).
 * Nokta ancak izinli çokgenin içinde ve hiçbir yasak çokgenin içinde
 * değilse geçerlidir. Sınırın üstü her zaman ihlaldir: izinli çokgenin
 * kenarı dışarı, yasak çokgenin kenarı yasak bölge sayılır (K-024).
 *
 * Koordinatlar harita çerçevesinde (map), santimetre, int16 (docs/protocol.md
 * §3). Hesap tamsayıyla yapılır: PC'de ve kartta aynı girdi aynı cevabı verir.
 *
 * Çokgenler basit olmalı (kenarlar kendini kesmez). Bu, veri üretilirken
 * denetlenir; burada denetlenmez. */
#ifndef GEOFENCE_H
#define GEOFENCE_H

#include <stdint.h>

/* Köşe sınırları: en kötü durumda 16 + 4 × 8 = 48 kenar denetlenir. Karar
 * süresi bu yüzden sınırlı kalır (K-013). */
#define GEOFENCE_ALLOWED_MAX             16u
#define GEOFENCE_FORBIDDEN_MAX            4u
#define GEOFENCE_FORBIDDEN_VERTICES_MAX   8u

typedef struct {
    int16_t x_cm;
    int16_t y_cm;
} geo_point_t;

typedef struct {
    uint8_t n;
    geo_point_t v[GEOFENCE_ALLOWED_MAX];
} geo_allowed_t;

typedef struct {
    uint8_t n;
    geo_point_t v[GEOFENCE_FORBIDDEN_VERTICES_MAX];
} geo_forbidden_t;

typedef struct {
    geo_allowed_t allowed;
    uint8_t n_forbidden;
    geo_forbidden_t forbidden[GEOFENCE_FORBIDDEN_MAX];
} geofence_t;

/* VERDICT'teki GOAL_OUTSIDE_ALLOWED ve GOAL_IN_FORBIDDEN'a karşılık gelir.
 * İkisi birden doğruysa (yasak bölge izinli çokgenin dışına taşıyorsa)
 * OUTSIDE_ALLOWED döner. */
typedef enum {
    GEOFENCE_OK = 0,
    GEOFENCE_OUTSIDE_ALLOWED,
    GEOFENCE_IN_FORBIDDEN,
} geofence_result_t;

/* Sınır geçersizse (izinli çokgen 3 köşeden az, herhangi bir sayı sınırını
 * aşıyor ya da yasak çokgen 3 köşeden az) her nokta için OUTSIDE_ALLOWED
 * döner: yanlış yapılandırılmış bir sınır hiçbir şeye izin vermez. */
geofence_result_t geofence_check(const geofence_t *g, geo_point_t p);

#endif /* GEOFENCE_H */
