/* Kurtarmanın sayıları ve varış denetimi (docs/RULES.md §5).
 *
 * Durum geçişlerinin kendisi guard/'da; burada yalnızca "ne zaman" ve "nereye
 * vardı" soruları. Donanıma dokunmaz, PC'de sınanır (firmware/tests/). */
#ifndef RECOVERY_H
#define RECOVERY_H

#include <stdbool.h>
#include <stdint.h>

#include "rules/geofence/geofence.h"

/* Üst üste bu kadar içerik reddi, kanal canlıyken kurtarmayı başlatır (§5.4).
 * Ajanın görev başına deneme sınırı bundan küçük olmalı (≤ 4, seçilen 3). */
#define RECOVERY_REJECT_LIMIT 5u

/* Varış toleransı (§5.3). Nav2'nin xy_goal_tolerance'ından (0,3 m) büyük
 * olmalı: küçük olursa Nav2 "vardım" deyip durur, kart varışı hiç görmez. */
#define RECOVERY_ARRIVAL_CM 35

/* Kurtarmada telemetri bu kadar gelmezse HOLD (K-047): kart varışı
 * göremiyorsa kör beklemez. */
#define RECOVERY_TELEMETRY_TIMEOUT_MS 500u

/* Kurtarma bu sürede bitmezse HOLD (K-047): Nav2 hedefte vazgeçerse kart
 * RECOVERY'de takılı kalmasın. Sahanın bir ucundan öbürüne ~60 m, 0,5 m/s ile
 * 2 dakikanın biraz üstü. Görüldü (2026-10-14): Nav2 kazı köşesinde vazgeçti,
 * kart süresiz RECOVERY'de kaldı. */
#define RECOVERY_TIMEOUT_MS 180000u

/* pos, goal'e RECOVERY_ARRIVAL_CM ya da daha yakınsa true. Tamsayıyla, karekök
 * almadan: int16 farkların karesi int32'ye sığmaz, int64 kullanılır. */
bool recovery_arrived(geo_point_t pos, geo_point_t goal);

#endif /* RECOVERY_H */
