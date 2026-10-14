/* Bekçinin karar katmanı: denetim sırası (docs/RULES.md §4) ve durum
 * makinesi (§5.2).
 *
 * Kuralların kendisi rules/ altında, kurtarmanın sayıları recovery/'de; burada
 * yalnızca sıraları ve sonuçları: hangi kural önce bakar, ret hangi gerekçeyle
 * döner, durum nasıl değişir. Donanıma dokunmaz, girdi alır ve karar döndürür:
 * PC'de sınanır (firmware/tests/test_guard.py). Çıktıları göndermek çağıranın işi.
 *
 * AUTH ve REPLAY buraya gelmeden kanal katmanında düşer (K-023). FRESHNESS
 * onlardan sonra, içerik kurallarından önce (guard_fresh). CONSISTENCY Faz 4'ün
 * sonraki adımında. */
#ifndef GUARD_H
#define GUARD_H

#include <stdbool.h>
#include <stdint.h>

#include "proto_msgs.h"
#include "site/site.h"

typedef struct {
    uint8_t state;           /* proto_board_state_t */
    uint8_t reject_streak;   /* üst üste içerik reddi (§5.4), 255'te doyar */
    geo_point_t recovery_goal;   /* RECOVERY'de gidilen nokta */
    bool recovery_timed;         /* girişten sonraki ilk guard_tick'te true olur */
    uint32_t recovery_t0_ms;     /* o tick'in zamanı */
    bool halt_pending;           /* HOLD'a girildi, araca bir kez HALT(0) gidecek (K-042) */
    int16_t prev_v_mm_s;         /* araca son GÖNDERİLEN hız (RULES §3.2); HOLD'da 0 */
    int16_t prev_w_mrad_s;
} guard_t;

typedef struct {
    proto_verdict_t verdict;
    bool send_goal;          /* hedef CAN'den araç tarafına gider: onaylı ya da kurtarma */
    proto_goal_t goal;
    bool send_halt;          /* WAIT/STOP: araca HALT(süre) gider, Nav2 hedefi iptal */
    proto_halt_t halt;
    bool send_speed_limit;   /* hiz_siniri kabul: araca SPEED_LIMIT_SET (Nav2'ye) */
    proto_speed_limit_set_t speed_limit;
} guard_decision_t;

/* Kart her zaman HOLD'da açılır (§5.2). */
void guard_init(guard_t *g);

/* GOTO_CMD: MODE → GEOFENCE. Coğrafi sınır reddinde ipucu, hedefe en yakın
 * güvenli nokta (docs/protocol.md §7.1). Üst üste RECOVERY_REJECT_LIMIT'inci
 * içerik reddinde, kanal canlıysa NORMAL → RECOVERY: aynı kararda ret VERDICT'i
 * ve başlangıca kurtarma hedefi (RECOVERY_HOME) çıkar (§5.2). */
void guard_goto(guard_t *g, const site_t *s, uint32_t seq, bool heartbeat_alive,
                const proto_goto_cmd_t *cmd, guard_decision_t *out);

/* FRESHNESS (RULES §3.3, §4. adım 4): ajan kanalının her imzalı çerçevesine,
 * REPLAY'den sonra. Tazeyse true. Değilse false; görev komutu ya da SIFIRLA ise
 * (VERDICT alanlar, protocol §7.2) *reply true ve out ret kararıdır (value yaş,
 * lo −50, hi 200). Hız komutu ve kalp atışı sessizce düşer. Ret serisine
 * sayılmaz (§5.4: taşımanın sorunu). Durumu değiştirmez. */
bool guard_fresh(uint32_t seq, uint8_t type, uint32_t now_ms, uint32_t ts_ms,
                 guard_decision_t *out, bool *reply);

/* SPEED_LIMIT_CMD (hiz_siniri): MODE → LIMIT (0 < değer ≤ 600 mm/s). Ret içerik
 * reddidir: seri artar, RECOVERY_REJECT_LIMIT'te kurtarma (guard_goto gibi);
 * VERDICT'te value istenen, lo..hi izinli aralık. Kabulde araca SPEED_LIMIT_SET,
 * seri sıfırlanır. */
void guard_speed_limit(guard_t *g, const site_t *s, uint32_t seq, bool heartbeat_alive,
                       const proto_speed_limit_cmd_t *cmd, guard_decision_t *out);

/* WAIT_CMD (bekle): görev komutu, NORMAL dışında MODE ile ret. Kabulde araca
 * HALT(süre): Nav2'nin hedefi iptal edilir, araç durur. Kabul ret serisini
 * sıfırlar (§5.4). CONSISTENCY Faz 4'ün sonraki adımında. */
void guard_wait(guard_t *g, uint32_t seq, const proto_wait_cmd_t *cmd, guard_decision_t *out);

/* STOP_CMD (dur): her durumda kabul edilir, araca HALT(0) (§2: durmak her
 * zaman güvenli). RECOVERY'de kurtarma biter → HOLD. Ret serisini sıfırlamaz:
 * araya "dur" koyarak kurtarmadan kaçılamasın (K-048). */
void guard_stop(guard_t *g, uint32_t seq, guard_decision_t *out);

/* RESET_CMD (SIFIRLA): yalnızca HOLD'da ve kalp atışı canlıyken kabul
 * edilir, HOLD → NORMAL. */
void guard_reset(guard_t *g, uint32_t seq, bool heartbeat_alive, guard_decision_t *out);

/* VELOCITY_CMD: NORMAL ve RECOVERY'de kırpılıp (LIMIT, §3.2, K-046) araca DRIVE
 * olarak gider (true, out doldurulur): kurtarmada aracı hedefe Nav2 götürür
 * (§5.2). Kırpıldıysa *clipped true (STATUS.clipped). HOLD'da gitmez (false),
 * araca giden sıfır hızı app.c gönderir. VERDICT yoktur (docs/protocol.md §7.2). */
bool guard_velocity(guard_t *g, const proto_velocity_cmd_t *cmd, proto_drive_t *out,
                    bool *clipped);

/* Kalp atışı zaman aşımı: NORMAL ya da RECOVERY → HOLD. Mandallıdır, kalp
 * atışı geri gelince kendiliğinden NORMAL'e dönülmez (§5.2). */
void guard_heartbeat_lost(guard_t *g);

/* TELEMETRY (araç konumu, 20 Hz). NORMAL'de araç izinli alanın dışında ya da
 * yasak bölgedeyse ve kanal canlıysa → RECOVERY, hedef araca en yakın güvenli
 * nokta (RECOVERY_SAFE). RECOVERY'de hedefe varınca → HOLD. HOLD'da etkisiz.
 * Araca gidecek bir kurtarma hedefi çıktıysa true döner, goal doldurulur. */
bool guard_telemetry(guard_t *g, const site_t *s, const proto_telemetry_t *tel,
                     bool heartbeat_alive, proto_goal_t *goal);

/* HOLD'a girildiyse bir kez true döner (sonra false): çağıran araca HALT(0)
 * gönderir, köprü Nav2'nin hedefini iptal eder (K-042). HOLD'a giden bütün
 * yollar (kalp atışı, varış, zaman kuralları, STOP) bunu kurar. */
bool guard_take_halt(guard_t *g);

/* Her döngüde. RECOVERY'nin zaman kuralları (K-047): son telemetri
 * RECOVERY_TELEMETRY_TIMEOUT_MS'den eskiyse ya da kurtarma RECOVERY_TIMEOUT_MS'den
 * uzun sürdüyse → HOLD. Süre, girişten sonraki ilk çağrıda başlar. Başka
 * durumlarda etkisiz. now_ms taşar (49 gün): fark işaretsiz alınır. */
void guard_tick(guard_t *g, uint32_t now_ms, uint32_t telemetry_age_ms);

#endif /* GUARD_H */
