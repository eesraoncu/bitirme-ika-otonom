#include "channel/channel.h"

#include <string.h>

#include "auth/key.h"
#include "timing/timing.h"

/* HELLO yayını ve HELLO_REQ cevabı aynı sınırı paylaşır: en fazla 500 ms'de
 * bir, yani saniyede 2 (docs/protocol.md §5.3). */
#define HELLO_PERIOD_MS   500u
#define STATUS_PERIOD_MS 1000u

void channel_init(channel_t *ch, serial_link_port_t port, uint8_t proto_ch,
                  uint32_t session_id)
{
    memset(ch, 0, sizeof *ch);
    ch->port = port;
    ch->proto_ch = proto_ch;
    ch->session_id = session_id;
    frame_rx_init(&ch->rx);
}

bool channel_send(channel_t *ch, uint8_t type, const uint8_t *payload, size_t len)
{
    if (ch->txq_len == CHANNEL_TX_QUEUE || len > PROTO_MAX_PAYLOAD_BYTES) {
        ch->tx_dropped++;
        return false;
    }
    channel_msg_t *m = &ch->txq[(ch->txq_head + ch->txq_len) % CHANNEL_TX_QUEUE];
    m->type = type;
    m->len = (uint8_t)len;
    memcpy(m->payload, payload, len);
    ch->txq_len++;
    return true;
}

static bool hello_due(const channel_t *ch, uint32_t now_ms)
{
    return !ch->hello_sent || now_ms - ch->last_hello_ms >= HELLO_PERIOD_MS;
}

static void send_hello(channel_t *ch, uint32_t now_ms, const channel_board_t *board)
{
    proto_hello_t h = {
        .session_id = ch->session_id,
        .last_rx_seq = ch->last_rx_seq,
        .schema_hash = PROTO_SCHEMA_HASH,
        .state = board->state,
    };
    uint8_t p[PROTO_SIZE_HELLO];
    proto_hello_encode(&h, p);
    if (channel_send(ch, PROTO_ID_HELLO, p, sizeof p)) {
        ch->hello_sent = true;
        ch->last_hello_ms = now_ms;
    }
}

static void send_status(channel_t *ch, const channel_board_t *board)
{
    proto_status_t s = {
        .state = board->state,
        .reject_streak = board->reject_streak,
        .frames_ok = ch->cnt.frames_ok,
        .err_framing = ch->cnt.err_framing,
        .err_crc = ch->cnt.err_crc,
        .err_type = ch->cnt.err_type,
        .err_auth = ch->cnt.err_auth,
        .err_replay = ch->cnt.err_replay,
        .err_fresh = ch->cnt.err_fresh,
        .clipped = ch->cnt.clipped,
        .telemetry_age_ms = board->telemetry_age_ms,
    };
    uint8_t p[PROTO_SIZE_STATUS];
    proto_status_encode(&s, p);
    (void)channel_send(ch, PROTO_ID_STATUS, p, sizeof p);
}

static void on_wire_frame(channel_t *ch, uint32_t now_ms, const channel_board_t *board,
                          channel_handler_t handler)
{
    frame_t f;
    switch (frame_decode(ch->rx.buf, ch->rx.len, auth_key, ch->session_id,
                         ch->proto_ch, PROTO_DIR_PC_TO_BOARD, &f)) {
    case FRAME_OK:
        break;
    case FRAME_ERR_FRAMING:
        ch->cnt.err_framing++;
        return;
    case FRAME_ERR_CRC:
        ch->cnt.err_crc++;
        return;
    case FRAME_ERR_TYPE:
        ch->cnt.err_type++;
        return;
    case FRAME_ERR_AUTH:
        ch->cnt.err_auth++;
        return;
    }

    /* İmzasız tek mesaj HELLO_REQ: köprü oturum kimliğini henüz bilmiyor
     * olabilir. Kartın durumunu değiştirmez, sayacı da değiştirmez: yoksa
     * imzasız mesaj yağdıran biri sayacı ileri itip köprünün meşru
     * çerçevelerini REPLAY ile düşürtebilirdi (docs/RULES.md §4). */
    if (!proto_msg_info(f.type)->auth) {
        ch->cnt.frames_ok++;
        if (hello_due(ch, now_ms)) {
            send_hello(ch, now_ms, board);
        }
        return;
    }

    /* REPLAY: sayaç son kabul edilenden büyük olmalı. Aradaki boşluklar
     * (kayıp çerçeveler) kabul edilir. Sayaç burada, imza doğrulandıktan
     * hemen sonra güncellenir, komut sonraki bir kuralda reddedilse bile
     * (docs/RULES.md §3.6). */
    if (f.seq <= ch->last_rx_seq) {
        ch->cnt.err_replay++;
        return;
    }
    ch->last_rx_seq = f.seq;
    ch->established = true;
    ch->cnt.frames_ok++;
    handler(ch, &f);
}

void channel_poll(channel_t *ch, uint32_t now_ms, const channel_board_t *board,
                  channel_handler_t handler)
{
    uint8_t buf[PROTO_MAX_WIRE_BYTES];
    size_t n = serial_link_read(ch->port, buf, sizeof buf);
    for (size_t i = 0; i < n; i++) {
        switch (frame_rx_push(&ch->rx, buf[i])) {
        case FRAME_RX_FRAME:
            /* Karar süresi burada başlar: çerçeve tamamlandı, henüz
             * çözülmedi. HMAC doğrulaması da süreye dahil. */
            ch->frame_t0 = dwt_cycles();
            timing_pin_high();
            on_wire_frame(ch, now_ms, board, handler);
            timing_pin_low();
            break;
        case FRAME_RX_OVERFLOW:
            ch->cnt.err_framing++;
            break;
        case FRAME_RX_NONE:
            break;
        }
    }
}

void channel_service(channel_t *ch, uint32_t now_ms, const channel_board_t *board)
{
    if (!ch->established && hello_due(ch, now_ms)) {
        send_hello(ch, now_ms, board);
    }
    if (now_ms - ch->last_status_ms >= STATUS_PERIOD_MS) {
        send_status(ch, board);
        ch->last_status_ms = now_ms;
    }

    /* Bir seferde bir çerçeve. Hat boşsa sıradakine sayaç ve zaman damgası
     * verilir, imzalanır ve gönderilir. */
    if (ch->txq_len == 0u || !serial_link_tx_ready(ch->port)) {
        return;
    }
    const channel_msg_t *m = &ch->txq[ch->txq_head];
    frame_t f = {
        .type = m->type,
        .seq = ++ch->tx_seq,
        .ts_ms = now_ms,
        .payload_len = m->len,
    };
    memcpy(f.payload, m->payload, m->len);
    uint8_t wire[PROTO_MAX_WIRE_BYTES];
    size_t w = frame_encode(&f, auth_key, ch->session_id, wire);
    if (w == 0u || !serial_link_send(ch->port, wire, w)) {
        ch->tx_dropped++;
    }
    ch->txq_head = (uint8_t)((ch->txq_head + 1u) % CHANNEL_TX_QUEUE);
    ch->txq_len--;
}
