/* Bekçinin karar katmanı: denetim sırası (docs/RULES.md §4) ve durum
 * makinesi (§5.2).
 *
 * Kuralların kendisi rules/ altında, burada yalnızca sıraları ve sonuçları:
 * hangi kural önce bakar, ret hangi gerekçeyle döner, durum nasıl değişir.
 * Donanıma dokunmaz, girdi alır ve karar döndürür: PC'de sınanır
 * (firmware/tests/test_guard.py). Çıktıları göndermek çağıranın işi.
 *
 * AUTH ve REPLAY buraya gelmeden kanal katmanında düşer (K-023). FRESHNESS,
 * LIMIT ve CONSISTENCY Faz 4'te; RECOVERY durumu da (üst üste 5 içerik
 * reddi, §5.4). Bu fazda sayaç tutulur ama geçiş yapılmaz. */
#ifndef GUARD_H
#define GUARD_H

#include <stdbool.h>
#include <stdint.h>

#include "proto_msgs.h"
#include "site/site.h"

typedef struct {
    uint8_t state;           /* proto_board_state_t */
    uint8_t reject_streak;   /* üst üste içerik reddi (§5.4), 255'te doyar */
} guard_t;

typedef struct {
    proto_verdict_t verdict;
    bool send_goal;          /* onaylı hedef CAN'den araç tarafına gider */
    proto_goal_t goal;
} guard_decision_t;

/* Kart her zaman HOLD'da açılır (§5.2). */
void guard_init(guard_t *g);

/* GOTO_CMD: MODE → GEOFENCE. Coğrafi sınır reddinde ipucu, hedefe en yakın
 * güvenli nokta (docs/protocol.md §7.1). */
void guard_goto(guard_t *g, const site_t *s, uint32_t seq,
                const proto_goto_cmd_t *cmd, guard_decision_t *out);

/* RESET_CMD (SIFIRLA): yalnızca HOLD'da ve kalp atışı canlıyken kabul
 * edilir, HOLD → NORMAL. */
void guard_reset(guard_t *g, uint32_t seq, bool heartbeat_alive, guard_decision_t *out);

/* VELOCITY_CMD (K-031, asgari aktarma): NORMAL'de araca DRIVE olarak aynen
 * gider (true, out doldurulur), başka her durumda gitmez (false). HOLD'da
 * araca giden sıfır hızı app.c gönderir. VERDICT yoktur (docs/protocol.md
 * §7.2). Kırpma (LIMIT, RULES §3.2) Faz 4'te. */
bool guard_velocity(const guard_t *g, const proto_velocity_cmd_t *cmd, proto_drive_t *out);

/* Kalp atışı zaman aşımı: NORMAL ya da RECOVERY → HOLD. Mandallıdır, kalp
 * atışı geri gelince kendiliğinden NORMAL'e dönülmez (§5.2). */
void guard_heartbeat_lost(guard_t *g);

#endif /* GUARD_H */
