#include "protocol/frame.h"

#include <string.h>

#include "auth/hmac_sha256.h"
#include "protocol/cobs.h"
#include "protocol/crc16.h"

/* Başlık ‖ etiket ‖ CRC: yüksüz, en kısa çerçeve */
#define MIN_RAW_BYTES (PROTO_HEADER_BYTES + PROTO_TAG_BYTES + PROTO_CRC_BYTES)

_Static_assert(COBS_ENCODED_MAX(PROTO_MAX_RAW_BYTES) + 1u <= PROTO_MAX_WIRE_BYTES,
               "En uzun çerçeve, ayracıyla birlikte hattın sınırına sığmalı");

/* etiket = HMAC(anahtar, session_id ‖ başlık ‖ yük)[0:8]. Oturum kimliği
 * hatta gönderilmez ama imzaya girer: kart yeniden başlayınca eski oturumun
 * çerçeveleri AUTH ile düşer (docs/protocol.md §5.2). */
static void compute_tag(const uint8_t key[FRAME_KEY_BYTES], uint32_t session_id,
                        const uint8_t *body, size_t body_len, uint8_t tag[PROTO_TAG_BYTES])
{
    uint8_t sid[4];
    uint8_t digest[SHA256_DIGEST_BYTES];
    hmac_sha256_ctx_t c;

    proto_put_u32(sid, session_id);
    hmac_sha256_init(&c, key, FRAME_KEY_BYTES);
    hmac_sha256_update(&c, sid, sizeof sid);
    hmac_sha256_update(&c, body, body_len);
    hmac_sha256_final(&c, digest);
    memcpy(tag, digest, PROTO_TAG_BYTES);
}

size_t frame_encode(const frame_t *f, const uint8_t key[FRAME_KEY_BYTES],
                    uint32_t session_id, uint8_t out[PROTO_MAX_WIRE_BYTES])
{
    const proto_msg_info_t *info = proto_msg_info(f->type);
    if (info == NULL || f->payload_len != info->size) {
        return 0;
    }

    uint8_t raw[PROTO_MAX_RAW_BYTES];
    size_t n = 0;

    /* Başlık, küçük uçtan: tip(1) seq(4) ts_ms(4) */
    raw[n] = f->type;
    proto_put_u32(&raw[n + 1u], f->seq);
    proto_put_u32(&raw[n + 5u], f->ts_ms);
    n += PROTO_HEADER_BYTES;

    memcpy(&raw[n], f->payload, f->payload_len);
    n += f->payload_len;

    if (info->auth) {
        compute_tag(key, session_id, raw, n, &raw[n]);
    } else {
        memset(&raw[n], 0, PROTO_TAG_BYTES);   /* HELLO_REQ: alan var, içi boş */
    }
    n += PROTO_TAG_BYTES;

    proto_put_u16(&raw[n], crc16_ccitt_false(raw, n));
    n += PROTO_CRC_BYTES;

    size_t w = cobs_encode(raw, n, out);
    out[w++] = PROTO_FRAME_DELIMITER;
    return w;
}

frame_result_t frame_decode(const uint8_t *wire, size_t len,
                            const uint8_t key[FRAME_KEY_BYTES], uint32_t session_id,
                            uint8_t channel, uint8_t dir, frame_t *out)
{
    /* Tampon en uzun geçerli çerçeveye (42) değil hattın sınırına göre:
     * 50 baytlık bir çerçeve burada FRAMING değil, Python'daki gibi TYPE
     * (yanlış uzunluk) sayılsın. İki taraf her girdiyi aynı türe koyar. */
    uint8_t raw[PROTO_MAX_WIRE_BYTES];
    size_t n;

    /* 1. COBS ve en küçük boy */
    if (!cobs_decode(wire, len, raw, sizeof raw, &n) || n < MIN_RAW_BYTES) {
        return FRAME_ERR_FRAMING;
    }

    /* 2. CRC: çöp veri üzerinde HMAC hesaplanmasın diye önce gelir */
    size_t crc_at = n - PROTO_CRC_BYTES;
    if (crc16_ccitt_false(raw, crc_at) != proto_get_u16(&raw[crc_at])) {
        return FRAME_ERR_CRC;
    }

    /* 3. Tip, yön, kanal, uzunluk */
    size_t body_len = crc_at - PROTO_TAG_BYTES;   /* başlık ‖ yük */
    size_t payload_len = body_len - PROTO_HEADER_BYTES;
    const proto_msg_info_t *info = proto_msg_info(raw[0]);
    if (info == NULL || info->dir != dir ||
        (info->channel != channel && info->channel != PROTO_CH_BOTH) ||
        payload_len != info->size) {
        return FRAME_ERR_TYPE;
    }

    /* 4. Etiket, sabit zamanlı karşılaştırılır */
    if (info->auth) {
        uint8_t tag[PROTO_TAG_BYTES];
        compute_tag(key, session_id, raw, body_len, tag);
        if (!hmac_tag_equal(tag, &raw[body_len], PROTO_TAG_BYTES)) {
            return FRAME_ERR_AUTH;
        }
    }

    out->type = raw[0];
    out->seq = proto_get_u32(&raw[1]);
    out->ts_ms = proto_get_u32(&raw[5]);
    memcpy(out->payload, &raw[PROTO_HEADER_BYTES], payload_len);
    out->payload_len = payload_len;
    return FRAME_OK;
}

void frame_rx_init(frame_rx_t *rx)
{
    rx->len = 0;
    rx->overflow = false;
    rx->handed = false;
}

frame_rx_event_t frame_rx_push(frame_rx_t *rx, uint8_t byte)
{
    if (rx->handed) {   /* Önceki çerçeve çağırana verilmişti, artık boşalt */
        rx->len = 0;
        rx->handed = false;
    }

    if (byte == PROTO_FRAME_DELIMITER) {
        frame_rx_event_t ev = FRAME_RX_NONE;
        if (rx->overflow) {
            ev = FRAME_RX_OVERFLOW;
        } else if (rx->len > 0u) {
            ev = FRAME_RX_FRAME;
        }
        rx->overflow = false;
        if (ev == FRAME_RX_FRAME) {
            rx->handed = true;
        } else {
            rx->len = 0;
        }
        return ev;
    }

    if (!rx->overflow) {
        rx->buf[rx->len++] = byte;
        /* Ayraçla birlikte sınırı aşacak: bu çerçeve atılır, sonraki ayraçta
         * tek bir taşma bildirilir. */
        if (rx->len >= PROTO_MAX_WIRE_BYTES) {
            rx->overflow = true;
            rx->len = 0;
        }
    }
    return FRAME_RX_NONE;
}
