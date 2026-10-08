/*
 * OTOMATİK ÜRETİLDİ. ELLE DÜZENLEMEYİN.
 * Kaynak: shared/protocol/messages.yaml
 * Üretici: tools/gen_protocol.py
 *
 * Mesaj tanımları, kodlayıcılar ve çözücüler. Çerçeveleme (COBS, CRC,
 * HMAC) burada değil, firmware/app/protocol/ altında elle yazılır ve
 * shared/protocol/test_vectors.json'daki baytları birebir üretmelidir.
 *
 * Tamsayılar little-endian. İşaretli çözmede (intN_t) dönüşümü GCC'nin
 * ikiye tümleyen davranışına dayanır.
 */
#ifndef PROTO_MSGS_H
#define PROTO_MSGS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PROTO_SCHEMA_VERSION     1u
#define PROTO_SCHEMA_HASH        0xD9092C66u
#define PROTO_FRAME_DELIMITER    0x00u
#define PROTO_HEADER_BYTES       9u
#define PROTO_TAG_BYTES          8u
#define PROTO_CRC_BYTES          2u
#define PROTO_MAX_PAYLOAD_BYTES  23u
#define PROTO_MAX_RAW_BYTES      42u
#define PROTO_MAX_WIRE_BYTES     64u

#define PROTO_CH_AGENT    1u
#define PROTO_CH_VEHICLE  2u
#define PROTO_CH_BOTH     3u
#define PROTO_DIR_PC_TO_BOARD  0u
#define PROTO_DIR_BOARD_TO_PC  1u

/* ---- Little-endian yardımcıları ------------------------------------ */

static inline void proto_put_u8(uint8_t *p, uint8_t v) { p[0] = v; }
static inline void proto_put_u16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
}
static inline void proto_put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
    p[2] = (uint8_t)((v >> 16) & 0xFFu);
    p[3] = (uint8_t)((v >> 24) & 0xFFu);
}
static inline void proto_put_i16(uint8_t *p, int16_t v) { proto_put_u16(p, (uint16_t)v); }
static inline void proto_put_i32(uint8_t *p, int32_t v) { proto_put_u32(p, (uint32_t)v); }

static inline uint8_t proto_get_u8(const uint8_t *p) { return p[0]; }
static inline uint16_t proto_get_u16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0] | (uint16_t)((uint16_t)p[1] << 8));
}
static inline uint32_t proto_get_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static inline int16_t proto_get_i16(const uint8_t *p) { return (int16_t)proto_get_u16(p); }
static inline int32_t proto_get_i32(const uint8_t *p) { return (int32_t)proto_get_u32(p); }

/* ---- Numaralandırmalar ---------------------------------------------- */

/* Kartın durum makinesi (docs/RULES.md §5.2) */
typedef enum {
    PROTO_BOARD_STATE_NORMAL = 0,
    PROTO_BOARD_STATE_RECOVERY = 1,
    PROTO_BOARD_STATE_HOLD = 2,
} proto_board_state_t;

static inline bool proto_board_state_is_valid(uint8_t v)
{
    switch (v) {
    case 0u:
    case 1u:
    case 2u:
        return true;
    default:
        return false;
    }
}

typedef enum {
    PROTO_RESULT_ACCEPTED = 0,
    PROTO_RESULT_REJECTED = 1,
} proto_result_t;

static inline bool proto_result_is_valid(uint8_t v)
{
    switch (v) {
    case 0u:
    case 1u:
        return true;
    default:
        return false;
    }
}

/* Karara yol açan kural (docs/RULES.md §2) */
typedef enum {
    PROTO_RULE_NONE = 0,
    PROTO_RULE_FRESHNESS = 3,
    PROTO_RULE_MODE = 4,
    PROTO_RULE_GEOFENCE = 5,
    PROTO_RULE_LIMIT = 6,
    PROTO_RULE_CONSISTENCY = 7,
} proto_rule_t;

static inline bool proto_rule_is_valid(uint8_t v)
{
    switch (v) {
    case 0u:
    case 3u:
    case 4u:
    case 5u:
    case 6u:
    case 7u:
        return true;
    default:
        return false;
    }
}

/* Kuralın alt nedeni. value/lo/hi/hint alanlarının anlamını belirler. */
typedef enum {
    PROTO_REASON_NONE = 0,
    PROTO_REASON_TOO_OLD = 10,
    PROTO_REASON_FROM_FUTURE = 11,
    PROTO_REASON_IN_RECOVERY = 20,
    PROTO_REASON_IN_HOLD = 21,
    PROTO_REASON_NOT_IN_HOLD = 22,
    PROTO_REASON_NO_HEARTBEAT = 23,
    PROTO_REASON_GOAL_OUTSIDE_ALLOWED = 30,
    PROTO_REASON_GOAL_IN_FORBIDDEN = 31,
    PROTO_REASON_ABOVE_MAX = 40,
    PROTO_REASON_NOT_POSITIVE = 41,
    PROTO_REASON_TOO_FAR = 50,
    PROTO_REASON_BELIEF_TOO_OLD = 51,
    PROTO_REASON_BELIEF_FROM_FUTURE = 52,
    PROTO_REASON_NO_TELEMETRY = 53,
} proto_reason_t;

static inline bool proto_reason_is_valid(uint8_t v)
{
    switch (v) {
    case 0u:
    case 10u:
    case 11u:
    case 20u:
    case 21u:
    case 22u:
    case 23u:
    case 30u:
    case 31u:
    case 40u:
    case 41u:
    case 50u:
    case 51u:
    case 52u:
    case 53u:
        return true;
    default:
        return false;
    }
}

/* Nav2'ye giden hedefin kaynağı (kayıt ve analiz için) */
typedef enum {
    PROTO_GOAL_SOURCE_AGENT = 0,
    PROTO_GOAL_SOURCE_RECOVERY_HOME = 1,
    PROTO_GOAL_SOURCE_RECOVERY_SAFE = 2,
} proto_goal_source_t;

static inline bool proto_goal_source_is_valid(uint8_t v)
{
    switch (v) {
    case 0u:
    case 1u:
    case 2u:
        return true;
    default:
        return false;
    }
}

/* ---- Mesajlar -------------------------------------------------------- */

/* HELLO_REQ  id=0x01  kanal=both  yön=pc_to_board  İMZASIZ
 * Köprü, oturum bilgisini ister. Kart HELLO ile cevap verir (en fazla saniyede 2 kez). İmzasızdır çünkü köprü oturum kimliğini henüz bilmiyor olabilir. Kartın durumunu değiştirmez.
 */
#define PROTO_ID_HELLO_REQ          0x01u
#define PROTO_SIZE_HELLO_REQ        0u

/* HELLO  id=0x81  kanal=both  yön=board_to_pc
 * Kart açılışta (oturum kurulana kadar 500 ms'de bir) ve HELLO_REQ'e cevaben gönderir. Başlıktaki ts_ms kartın o anki saatidir.
 */
#define PROTO_ID_HELLO              0x81u
#define PROTO_SIZE_HELLO            13u
typedef struct {
    uint32_t session_id;
    uint32_t last_rx_seq;
    uint32_t schema_hash;
    uint8_t state;  /* enum BoardState */
} proto_hello_t;

static inline void proto_hello_encode(const proto_hello_t *m, uint8_t *buf)
{
    proto_put_u32(buf + 0, m->session_id);
    proto_put_u32(buf + 4, m->last_rx_seq);
    proto_put_u32(buf + 8, m->schema_hash);
    proto_put_u8(buf + 12, m->state);
}

static inline bool proto_hello_decode(const uint8_t *buf, size_t len, proto_hello_t *m)
{
    if (len != PROTO_SIZE_HELLO) {
        return false;
    }
    m->session_id = proto_get_u32(buf + 0);
    m->last_rx_seq = proto_get_u32(buf + 4);
    m->schema_hash = proto_get_u32(buf + 8);
    m->state = proto_get_u8(buf + 12);
    if (!proto_board_state_is_valid(m->state)) {
        return false;
    }
    return true;
}

/* HEARTBEAT  id=0x02  kanal=agent  yön=pc_to_board
 * Köprü 100 ms'de bir gönderir. Aynı zamanda saat eşitleme örneğidir. Zaman aşımı 500 ms (docs/RULES.md §3.5).
 */
#define PROTO_ID_HEARTBEAT          0x02u
#define PROTO_SIZE_HEARTBEAT        4u
typedef struct {
    uint32_t echo_pc_ms;  /* ms */
} proto_heartbeat_t;

static inline void proto_heartbeat_encode(const proto_heartbeat_t *m, uint8_t *buf)
{
    proto_put_u32(buf + 0, m->echo_pc_ms);
}

static inline bool proto_heartbeat_decode(const uint8_t *buf, size_t len, proto_heartbeat_t *m)
{
    if (len != PROTO_SIZE_HEARTBEAT) {
        return false;
    }
    m->echo_pc_ms = proto_get_u32(buf + 0);
    return true;
}

/* HEARTBEAT_ACK  id=0x82  kanal=agent  yön=board_to_pc
 * Her HEARTBEAT'e cevap. Başlıktaki ts_ms, saat eşitlemesi için kartın saatidir.
 */
#define PROTO_ID_HEARTBEAT_ACK      0x82u
#define PROTO_SIZE_HEARTBEAT_ACK    6u
typedef struct {
    uint32_t echo_pc_ms;  /* ms */
    uint8_t state;  /* enum BoardState */
    uint8_t reject_streak;
} proto_heartbeat_ack_t;

static inline void proto_heartbeat_ack_encode(const proto_heartbeat_ack_t *m, uint8_t *buf)
{
    proto_put_u32(buf + 0, m->echo_pc_ms);
    proto_put_u8(buf + 4, m->state);
    proto_put_u8(buf + 5, m->reject_streak);
}

static inline bool proto_heartbeat_ack_decode(const uint8_t *buf, size_t len, proto_heartbeat_ack_t *m)
{
    if (len != PROTO_SIZE_HEARTBEAT_ACK) {
        return false;
    }
    m->echo_pc_ms = proto_get_u32(buf + 0);
    m->state = proto_get_u8(buf + 4);
    m->reject_streak = proto_get_u8(buf + 5);
    if (!proto_board_state_is_valid(m->state)) {
        return false;
    }
    return true;
}

/* STATUS  id=0x83  kanal=both  yön=board_to_pc
 * Saniyede bir, o kanala ait sayaçlar. Açılıştan beri birikimlidir, uint16 olarak taşar. "Bozuk çerçeve sessizce atılmaz, sayılır ve raporlanır."
 */
#define PROTO_ID_STATUS             0x83u
#define PROTO_SIZE_STATUS           20u
typedef struct {
    uint8_t state;  /* enum BoardState */
    uint8_t reject_streak;
    uint16_t frames_ok;
    uint16_t err_framing;
    uint16_t err_crc;
    uint16_t err_type;
    uint16_t err_auth;
    uint16_t err_replay;
    uint16_t err_fresh;
    uint16_t clipped;
    uint16_t telemetry_age_ms;  /* ms */
} proto_status_t;

static inline void proto_status_encode(const proto_status_t *m, uint8_t *buf)
{
    proto_put_u8(buf + 0, m->state);
    proto_put_u8(buf + 1, m->reject_streak);
    proto_put_u16(buf + 2, m->frames_ok);
    proto_put_u16(buf + 4, m->err_framing);
    proto_put_u16(buf + 6, m->err_crc);
    proto_put_u16(buf + 8, m->err_type);
    proto_put_u16(buf + 10, m->err_auth);
    proto_put_u16(buf + 12, m->err_replay);
    proto_put_u16(buf + 14, m->err_fresh);
    proto_put_u16(buf + 16, m->clipped);
    proto_put_u16(buf + 18, m->telemetry_age_ms);
}

static inline bool proto_status_decode(const uint8_t *buf, size_t len, proto_status_t *m)
{
    if (len != PROTO_SIZE_STATUS) {
        return false;
    }
    m->state = proto_get_u8(buf + 0);
    m->reject_streak = proto_get_u8(buf + 1);
    m->frames_ok = proto_get_u16(buf + 2);
    m->err_framing = proto_get_u16(buf + 4);
    m->err_crc = proto_get_u16(buf + 6);
    m->err_type = proto_get_u16(buf + 8);
    m->err_auth = proto_get_u16(buf + 10);
    m->err_replay = proto_get_u16(buf + 12);
    m->err_fresh = proto_get_u16(buf + 14);
    m->clipped = proto_get_u16(buf + 16);
    m->telemetry_age_ms = proto_get_u16(buf + 18);
    if (!proto_board_state_is_valid(m->state)) {
        return false;
    }
    return true;
}

/* VELOCITY_CMD  id=0x10  kanal=agent  yön=pc_to_board
 * Nav2'nin hız komutu, 20 Hz. İhlalde kırpılır, VERDICT gönderilmez.
 */
#define PROTO_ID_VELOCITY_CMD       0x10u
#define PROTO_SIZE_VELOCITY_CMD     4u
typedef struct {
    int16_t v_mm_s;  /* mm/s */
    int16_t w_mrad_s;  /* mrad/s */
} proto_velocity_cmd_t;

static inline void proto_velocity_cmd_encode(const proto_velocity_cmd_t *m, uint8_t *buf)
{
    proto_put_i16(buf + 0, m->v_mm_s);
    proto_put_i16(buf + 2, m->w_mrad_s);
}

static inline bool proto_velocity_cmd_decode(const uint8_t *buf, size_t len, proto_velocity_cmd_t *m)
{
    if (len != PROTO_SIZE_VELOCITY_CMD) {
        return false;
    }
    m->v_mm_s = proto_get_i16(buf + 0);
    m->w_mrad_s = proto_get_i16(buf + 2);
    return true;
}

/* GOTO_CMD  id=0x20  kanal=agent  yön=pc_to_board
 * Ajan: git(yer). Denetim: GEOFENCE, CONSISTENCY.
 */
#define PROTO_ID_GOTO_CMD           0x20u
#define PROTO_SIZE_GOTO_CMD         14u
typedef struct {
    int16_t goal_x_cm;  /* cm */
    int16_t goal_y_cm;  /* cm */
    int16_t goal_yaw_mrad;  /* mrad */
    int16_t belief_x_cm;  /* cm */
    int16_t belief_y_cm;  /* cm */
    uint32_t belief_ts_ms;  /* ms */
} proto_goto_cmd_t;

static inline void proto_goto_cmd_encode(const proto_goto_cmd_t *m, uint8_t *buf)
{
    proto_put_i16(buf + 0, m->goal_x_cm);
    proto_put_i16(buf + 2, m->goal_y_cm);
    proto_put_i16(buf + 4, m->goal_yaw_mrad);
    proto_put_i16(buf + 6, m->belief_x_cm);
    proto_put_i16(buf + 8, m->belief_y_cm);
    proto_put_u32(buf + 10, m->belief_ts_ms);
}

static inline bool proto_goto_cmd_decode(const uint8_t *buf, size_t len, proto_goto_cmd_t *m)
{
    if (len != PROTO_SIZE_GOTO_CMD) {
        return false;
    }
    m->goal_x_cm = proto_get_i16(buf + 0);
    m->goal_y_cm = proto_get_i16(buf + 2);
    m->goal_yaw_mrad = proto_get_i16(buf + 4);
    m->belief_x_cm = proto_get_i16(buf + 6);
    m->belief_y_cm = proto_get_i16(buf + 8);
    m->belief_ts_ms = proto_get_u32(buf + 10);
    return true;
}

/* WAIT_CMD  id=0x21  kanal=agent  yön=pc_to_board
 * Ajan: bekle(süre). Denetim: CONSISTENCY. Araç tarafına HALT(süre) olarak gider.
 */
#define PROTO_ID_WAIT_CMD           0x21u
#define PROTO_SIZE_WAIT_CMD         10u
typedef struct {
    uint16_t duration_s;  /* s */
    int16_t belief_x_cm;  /* cm */
    int16_t belief_y_cm;  /* cm */
    uint32_t belief_ts_ms;  /* ms */
} proto_wait_cmd_t;

static inline void proto_wait_cmd_encode(const proto_wait_cmd_t *m, uint8_t *buf)
{
    proto_put_u16(buf + 0, m->duration_s);
    proto_put_i16(buf + 2, m->belief_x_cm);
    proto_put_i16(buf + 4, m->belief_y_cm);
    proto_put_u32(buf + 6, m->belief_ts_ms);
}

static inline bool proto_wait_cmd_decode(const uint8_t *buf, size_t len, proto_wait_cmd_t *m)
{
    if (len != PROTO_SIZE_WAIT_CMD) {
        return false;
    }
    m->duration_s = proto_get_u16(buf + 0);
    m->belief_x_cm = proto_get_i16(buf + 2);
    m->belief_y_cm = proto_get_i16(buf + 4);
    m->belief_ts_ms = proto_get_u32(buf + 6);
    return true;
}

/* SPEED_LIMIT_CMD  id=0x22  kanal=agent  yön=pc_to_board
 * Ajan: hiz_siniri(değer). Denetim: LIMIT (0 < değer ≤ 600), CONSISTENCY.
 */
#define PROTO_ID_SPEED_LIMIT_CMD    0x22u
#define PROTO_SIZE_SPEED_LIMIT_CMD  10u
typedef struct {
    uint16_t limit_mm_s;  /* mm/s */
    int16_t belief_x_cm;  /* cm */
    int16_t belief_y_cm;  /* cm */
    uint32_t belief_ts_ms;  /* ms */
} proto_speed_limit_cmd_t;

static inline void proto_speed_limit_cmd_encode(const proto_speed_limit_cmd_t *m, uint8_t *buf)
{
    proto_put_u16(buf + 0, m->limit_mm_s);
    proto_put_i16(buf + 2, m->belief_x_cm);
    proto_put_i16(buf + 4, m->belief_y_cm);
    proto_put_u32(buf + 6, m->belief_ts_ms);
}

static inline bool proto_speed_limit_cmd_decode(const uint8_t *buf, size_t len, proto_speed_limit_cmd_t *m)
{
    if (len != PROTO_SIZE_SPEED_LIMIT_CMD) {
        return false;
    }
    m->limit_mm_s = proto_get_u16(buf + 0);
    m->belief_x_cm = proto_get_i16(buf + 2);
    m->belief_y_cm = proto_get_i16(buf + 4);
    m->belief_ts_ms = proto_get_u32(buf + 6);
    return true;
}

/* STOP_CMD  id=0x23  kanal=agent  yön=pc_to_board
 * Ajan: dur(). Durmak her zaman güvenlidir: MODE ve içerik kuralları uygulanmaz, konum inancı taşımaz. Yalnızca AUTH, REPLAY, FRESHNESS.
 */
#define PROTO_ID_STOP_CMD           0x23u
#define PROTO_SIZE_STOP_CMD         0u

/* RESET_CMD  id=0x30  kanal=agent  yön=pc_to_board
 * SIFIRLA. Yalnızca HOLD'da ve kalp atışı canlıyken kabul edilir. HOLD → NORMAL.
 */
#define PROTO_ID_RESET_CMD          0x30u
#define PROTO_SIZE_RESET_CMD        0u

/* VERDICT  id=0x90  kanal=agent  yön=board_to_pc
 * İmzası doğrulanmış her görev komutu ve RESET_CMD için karar. Kart her yapılandırmada TAM gerekçeyi gönderir. C yapılandırmasında gerekçeyi ajandan köprü gizler (docs/protocol.md §7).
 */
#define PROTO_ID_VERDICT            0x90u
#define PROTO_SIZE_VERDICT          23u
typedef struct {
    uint32_t ref_seq;
    uint8_t result;  /* enum Result */
    uint8_t rule;  /* enum Rule */
    uint8_t reason;  /* enum Reason */
    int32_t value;
    int32_t lo;
    int32_t hi;
    int16_t hint_x_cm;  /* cm */
    int16_t hint_y_cm;  /* cm */
} proto_verdict_t;

static inline void proto_verdict_encode(const proto_verdict_t *m, uint8_t *buf)
{
    proto_put_u32(buf + 0, m->ref_seq);
    proto_put_u8(buf + 4, m->result);
    proto_put_u8(buf + 5, m->rule);
    proto_put_u8(buf + 6, m->reason);
    proto_put_i32(buf + 7, m->value);
    proto_put_i32(buf + 11, m->lo);
    proto_put_i32(buf + 15, m->hi);
    proto_put_i16(buf + 19, m->hint_x_cm);
    proto_put_i16(buf + 21, m->hint_y_cm);
}

static inline bool proto_verdict_decode(const uint8_t *buf, size_t len, proto_verdict_t *m)
{
    if (len != PROTO_SIZE_VERDICT) {
        return false;
    }
    m->ref_seq = proto_get_u32(buf + 0);
    m->result = proto_get_u8(buf + 4);
    m->rule = proto_get_u8(buf + 5);
    m->reason = proto_get_u8(buf + 6);
    m->value = proto_get_i32(buf + 7);
    m->lo = proto_get_i32(buf + 11);
    m->hi = proto_get_i32(buf + 15);
    m->hint_x_cm = proto_get_i16(buf + 19);
    m->hint_y_cm = proto_get_i16(buf + 21);
    if (!proto_result_is_valid(m->result)) {
        return false;
    }
    if (!proto_rule_is_valid(m->rule)) {
        return false;
    }
    if (!proto_reason_is_valid(m->reason)) {
        return false;
    }
    return true;
}

/* TELEMETRY  id=0x40  kanal=vehicle  yön=pc_to_board  can_id=0x200
 * Aracın harita çerçevesindeki konumu, 20 Hz. Yalnızca araç kanalından kabul edilir: ajan tarafı telemetri uyduramaz (docs/protocol.md §2).
 */
#define PROTO_ID_TELEMETRY          0x40u
#define PROTO_SIZE_TELEMETRY        6u
#define PROTO_CAN_ID_TELEMETRY      0x200u
typedef struct {
    int16_t x_cm;  /* cm */
    int16_t y_cm;  /* cm */
    int16_t yaw_mrad;  /* mrad */
} proto_telemetry_t;

static inline void proto_telemetry_encode(const proto_telemetry_t *m, uint8_t *buf)
{
    proto_put_i16(buf + 0, m->x_cm);
    proto_put_i16(buf + 2, m->y_cm);
    proto_put_i16(buf + 4, m->yaw_mrad);
}

static inline bool proto_telemetry_decode(const uint8_t *buf, size_t len, proto_telemetry_t *m)
{
    if (len != PROTO_SIZE_TELEMETRY) {
        return false;
    }
    m->x_cm = proto_get_i16(buf + 0);
    m->y_cm = proto_get_i16(buf + 2);
    m->yaw_mrad = proto_get_i16(buf + 4);
    return true;
}

/* HALT  id=0xA3  kanal=vehicle  yön=board_to_pc  can_id=0x100
 * Nav2 hedefini iptal et ve dur. duration_s = 0 → süresiz (STOP_CMD).
 */
#define PROTO_ID_HALT               0xA3u
#define PROTO_SIZE_HALT             2u
#define PROTO_CAN_ID_HALT           0x100u
typedef struct {
    uint16_t duration_s;  /* s */
} proto_halt_t;

static inline void proto_halt_encode(const proto_halt_t *m, uint8_t *buf)
{
    proto_put_u16(buf + 0, m->duration_s);
}

static inline bool proto_halt_decode(const uint8_t *buf, size_t len, proto_halt_t *m)
{
    if (len != PROTO_SIZE_HALT) {
        return false;
    }
    m->duration_s = proto_get_u16(buf + 0);
    return true;
}

/* DRIVE  id=0xA0  kanal=vehicle  yön=board_to_pc  can_id=0x110
 * Onaylı (gerekirse kırpılmış) hız komutu. HOLD'da 20 Hz sıfır hız.
 */
#define PROTO_ID_DRIVE              0xA0u
#define PROTO_SIZE_DRIVE            4u
#define PROTO_CAN_ID_DRIVE          0x110u
typedef struct {
    int16_t v_mm_s;  /* mm/s */
    int16_t w_mrad_s;  /* mrad/s */
} proto_drive_t;

static inline void proto_drive_encode(const proto_drive_t *m, uint8_t *buf)
{
    proto_put_i16(buf + 0, m->v_mm_s);
    proto_put_i16(buf + 2, m->w_mrad_s);
}

static inline bool proto_drive_decode(const uint8_t *buf, size_t len, proto_drive_t *m)
{
    if (len != PROTO_SIZE_DRIVE) {
        return false;
    }
    m->v_mm_s = proto_get_i16(buf + 0);
    m->w_mrad_s = proto_get_i16(buf + 2);
    return true;
}

/* GOAL  id=0xA1  kanal=vehicle  yön=board_to_pc  can_id=0x120
 * Onaylı hedef. Köprü Nav2'ye iletir.
 */
#define PROTO_ID_GOAL               0xA1u
#define PROTO_SIZE_GOAL             7u
#define PROTO_CAN_ID_GOAL           0x120u
typedef struct {
    int16_t x_cm;  /* cm */
    int16_t y_cm;  /* cm */
    int16_t yaw_mrad;  /* mrad */
    uint8_t source;  /* enum GoalSource */
} proto_goal_t;

static inline void proto_goal_encode(const proto_goal_t *m, uint8_t *buf)
{
    proto_put_i16(buf + 0, m->x_cm);
    proto_put_i16(buf + 2, m->y_cm);
    proto_put_i16(buf + 4, m->yaw_mrad);
    proto_put_u8(buf + 6, m->source);
}

static inline bool proto_goal_decode(const uint8_t *buf, size_t len, proto_goal_t *m)
{
    if (len != PROTO_SIZE_GOAL) {
        return false;
    }
    m->x_cm = proto_get_i16(buf + 0);
    m->y_cm = proto_get_i16(buf + 2);
    m->yaw_mrad = proto_get_i16(buf + 4);
    m->source = proto_get_u8(buf + 6);
    if (!proto_goal_source_is_valid(m->source)) {
        return false;
    }
    return true;
}

/* SPEED_LIMIT_SET  id=0xA2  kanal=vehicle  yön=board_to_pc  can_id=0x130
 * Onaylı hız sınırı. Köprü Nav2'nin hız sınırı konusuna iletir.
 */
#define PROTO_ID_SPEED_LIMIT_SET    0xA2u
#define PROTO_SIZE_SPEED_LIMIT_SET  2u
#define PROTO_CAN_ID_SPEED_LIMIT_SET 0x130u
typedef struct {
    uint16_t limit_mm_s;  /* mm/s */
} proto_speed_limit_set_t;

static inline void proto_speed_limit_set_encode(const proto_speed_limit_set_t *m, uint8_t *buf)
{
    proto_put_u16(buf + 0, m->limit_mm_s);
}

static inline bool proto_speed_limit_set_decode(const uint8_t *buf, size_t len, proto_speed_limit_set_t *m)
{
    if (len != PROTO_SIZE_SPEED_LIMIT_SET) {
        return false;
    }
    m->limit_mm_s = proto_get_u16(buf + 0);
    return true;
}

/* ---- Mesaj tablosu ---------------------------------------------------- */

typedef struct {
    uint8_t id;
    uint8_t size;
    uint8_t channel;  /* PROTO_CH_*  */
    uint8_t dir;      /* PROTO_DIR_* */
    bool auth;
    bool has_can_id;
    uint16_t can_id;
    const char *name;
} proto_msg_info_t;

/* Bilinmeyen kimlikte NULL döner (STATUS.err_type). */
static inline const proto_msg_info_t *proto_msg_info(uint8_t id)
{
    static const proto_msg_info_t table[] = {
        {PROTO_ID_HELLO_REQ, PROTO_SIZE_HELLO_REQ, PROTO_CH_BOTH, PROTO_DIR_PC_TO_BOARD, false, false, 0u, "HELLO_REQ"},
        {PROTO_ID_HELLO, PROTO_SIZE_HELLO, PROTO_CH_BOTH, PROTO_DIR_BOARD_TO_PC, true, false, 0u, "HELLO"},
        {PROTO_ID_HEARTBEAT, PROTO_SIZE_HEARTBEAT, PROTO_CH_AGENT, PROTO_DIR_PC_TO_BOARD, true, false, 0u, "HEARTBEAT"},
        {PROTO_ID_HEARTBEAT_ACK, PROTO_SIZE_HEARTBEAT_ACK, PROTO_CH_AGENT, PROTO_DIR_BOARD_TO_PC, true, false, 0u, "HEARTBEAT_ACK"},
        {PROTO_ID_STATUS, PROTO_SIZE_STATUS, PROTO_CH_BOTH, PROTO_DIR_BOARD_TO_PC, true, false, 0u, "STATUS"},
        {PROTO_ID_VELOCITY_CMD, PROTO_SIZE_VELOCITY_CMD, PROTO_CH_AGENT, PROTO_DIR_PC_TO_BOARD, true, false, 0u, "VELOCITY_CMD"},
        {PROTO_ID_GOTO_CMD, PROTO_SIZE_GOTO_CMD, PROTO_CH_AGENT, PROTO_DIR_PC_TO_BOARD, true, false, 0u, "GOTO_CMD"},
        {PROTO_ID_WAIT_CMD, PROTO_SIZE_WAIT_CMD, PROTO_CH_AGENT, PROTO_DIR_PC_TO_BOARD, true, false, 0u, "WAIT_CMD"},
        {PROTO_ID_SPEED_LIMIT_CMD, PROTO_SIZE_SPEED_LIMIT_CMD, PROTO_CH_AGENT, PROTO_DIR_PC_TO_BOARD, true, false, 0u, "SPEED_LIMIT_CMD"},
        {PROTO_ID_STOP_CMD, PROTO_SIZE_STOP_CMD, PROTO_CH_AGENT, PROTO_DIR_PC_TO_BOARD, true, false, 0u, "STOP_CMD"},
        {PROTO_ID_RESET_CMD, PROTO_SIZE_RESET_CMD, PROTO_CH_AGENT, PROTO_DIR_PC_TO_BOARD, true, false, 0u, "RESET_CMD"},
        {PROTO_ID_VERDICT, PROTO_SIZE_VERDICT, PROTO_CH_AGENT, PROTO_DIR_BOARD_TO_PC, true, false, 0u, "VERDICT"},
        {PROTO_ID_TELEMETRY, PROTO_SIZE_TELEMETRY, PROTO_CH_VEHICLE, PROTO_DIR_PC_TO_BOARD, true, true, 0x200u, "TELEMETRY"},
        {PROTO_ID_HALT, PROTO_SIZE_HALT, PROTO_CH_VEHICLE, PROTO_DIR_BOARD_TO_PC, true, true, 0x100u, "HALT"},
        {PROTO_ID_DRIVE, PROTO_SIZE_DRIVE, PROTO_CH_VEHICLE, PROTO_DIR_BOARD_TO_PC, true, true, 0x110u, "DRIVE"},
        {PROTO_ID_GOAL, PROTO_SIZE_GOAL, PROTO_CH_VEHICLE, PROTO_DIR_BOARD_TO_PC, true, true, 0x120u, "GOAL"},
        {PROTO_ID_SPEED_LIMIT_SET, PROTO_SIZE_SPEED_LIMIT_SET, PROTO_CH_VEHICLE, PROTO_DIR_BOARD_TO_PC, true, true, 0x130u, "SPEED_LIMIT_SET"},
    };
    for (size_t i = 0; i < sizeof table / sizeof table[0]; ++i) {
        if (table[i].id == id) {
            return &table[i];
        }
    }
    return NULL;
}

#endif /* PROTO_MSGS_H */
