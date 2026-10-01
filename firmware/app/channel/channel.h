/* Bir seri kanalın protokol durumu (docs/protocol.md §4.7, §5).
 *
 * serial_link bayt taşır, frame çerçeveyi çözer; ikisi de durumsuz. Durum
 * burada: son kabul edilen sayaç (REPLAY), STATUS sayaçları, giden sayaç ve
 * oturumun bu kanalda kurulup kurulmadığı. Her kanalın kendi sayaçları
 * vardır, oturum kimliği ortaktır (§5.3).
 *
 * Gelen çerçeve sırası: COBS → CRC → tip/yön/kanal/uzunluk → HMAC
 * (frame_decode) → sayaç (burada). Bu adımlarda reddedilen çerçeveye cevap
 * verilmez, yalnızca ilgili sayaç artar (§4.7). */
#ifndef CHANNEL_H
#define CHANNEL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "links/serial_link.h"
#include "protocol/frame.h"

/* Gönderilmeyi bekleyen en fazla mesaj. Hat bir çerçeveyi ~4 ms'de taşır;
 * o sırada gelen cevaplar (ör. STATUS gönderilirken HEARTBEAT_ACK) burada
 * bekler. */
#define CHANNEL_TX_QUEUE 4u

/* STATUS'taki kanal sayaçları. uint16, taşınca sıfıra döner (messages.yaml). */
typedef struct {
    uint16_t frames_ok;     /* tüm denetimleri geçen */
    uint16_t err_framing;
    uint16_t err_crc;
    uint16_t err_type;
    uint16_t err_auth;
    uint16_t err_replay;
    uint16_t err_fresh;     /* tazelik kuralı (Faz 4) artıracak */
    uint16_t clipped;       /* hız limiti kuralı artıracak */
} channel_counters_t;

typedef struct {
    uint8_t type;
    uint8_t len;
    uint8_t payload[PROTO_MAX_PAYLOAD_BYTES];
} channel_msg_t;

typedef struct {
    serial_link_port_t port;
    uint8_t proto_ch;          /* PROTO_CH_AGENT ya da PROTO_CH_VEHICLE */
    uint32_t session_id;
    frame_rx_t rx;
    uint32_t last_rx_seq;      /* son kabul edilen sayaç, HELLO'da duyurulur */
    uint32_t tx_seq;           /* son gönderilen sayaç */
    bool established;          /* bu kanaldan imzalı bir çerçeve kabul edildi */
    bool hello_sent;           /* last_hello_ms geçerli */
    uint32_t last_hello_ms;
    uint32_t last_status_ms;
    channel_counters_t cnt;
    channel_msg_t txq[CHANNEL_TX_QUEUE];
    uint8_t txq_head;
    uint8_t txq_len;
    uint32_t tx_dropped;       /* kuyruk doluydu. STATUS'ta yok, RAM'den okunur */
    uint32_t frame_t0;         /* son çerçevenin tamamlandığı an (DWT çevrimi).
                                  Handler karar süresini bundan ölçer (K-009) */
} channel_t;

/* Kartın HELLO ve STATUS'a giren, tek bir kanala ait olmayan durumu. */
typedef struct {
    uint8_t state;             /* proto_board_state_t */
    uint8_t reject_streak;
    uint16_t telemetry_age_ms;
} channel_board_t;

/* Tüm denetimleri geçen bir çerçeve için çağrılır. Çerçevenin ayracı
 * geldiğinden beri ölçüm pini (PA8) 1'dir, handler dönünce 0 olur. */
typedef void (*channel_handler_t)(channel_t *ch, const frame_t *f);

void channel_init(channel_t *ch, serial_link_port_t port, uint8_t proto_ch,
                  uint32_t session_id);

/* Porttan gelen baytları işler. Denetimleri geçen her çerçeve handler'a
 * verilir. HELLO_REQ'i kanal kendisi cevaplar, handler'a vermez. Bir
 * çağrıda en fazla PROTO_MAX_WIRE_BYTES bayt okunur, yani beklemez. */
void channel_poll(channel_t *ch, uint32_t now_ms, const channel_board_t *board,
                  channel_handler_t handler);

/* HELLO yayını (oturum kurulana kadar 500 ms'de bir), STATUS (saniyede
 * bir) ve gönderme kuyruğu. Her döngü turunda çağrılır. */
void channel_service(channel_t *ch, uint32_t now_ms, const channel_board_t *board);

/* Mesajı gönderme kuyruğuna koyar. Sayaç ve zaman damgası çerçeve hatta
 * çıkarken verilir: HEARTBEAT_ACK'in zamanı kuyrukta beklediği süreyi
 * içermesin (saat eşitleme, docs/protocol.md §6). Kuyruk doluysa false. */
bool channel_send(channel_t *ch, uint8_t type, const uint8_t *payload, size_t len);

#endif /* CHANNEL_H */
