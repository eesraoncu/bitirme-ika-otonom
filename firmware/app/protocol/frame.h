/* Çerçeve katmanı (docs/protocol.md §4). Python'daki frame.py'nin karşılığı:
 *
 *   COBS( başlık ‖ yük ‖ etiket ‖ CRC ) ‖ 0x00
 *
 * Mesajların boyu, imzası, kanalı ve yönü üretilmiş tablodan (proto_msg_info,
 * messages.yaml) gelir; burada hiçbir mesaj elle tanımlanmaz.
 *
 * Bu katman durumsuzdur. Sayaç (tekrar) ve tazelik alıcının durumuna bağlı
 * olduğu için burada değil, alıcıda denetlenir. STATUS sayaçlarını da
 * çağıran tutar: frame_decode() yalnızca sonucun türünü döndürür. */
#ifndef FRAME_H
#define FRAME_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "proto_msgs.h"

#define FRAME_KEY_BYTES 32u

/* Reddin türü. Her biri STATUS'taki bir sayaca karşılık gelir
 * (docs/protocol.md §4.7). */
typedef enum {
    FRAME_OK = 0,
    FRAME_ERR_FRAMING,   /* COBS hatası, çok kısa ya da taşan çerçeve → err_framing */
    FRAME_ERR_CRC,       /* hat bozdu                                 → err_crc */
    FRAME_ERR_TYPE,      /* bilinmeyen tip, yanlış yön/kanal/uzunluk  → err_type */
    FRAME_ERR_AUTH,      /* etiket tutmuyor: yanlış anahtar ya da oturum → err_auth */
} frame_result_t;

typedef struct {
    uint8_t type;
    uint32_t seq;
    uint32_t ts_ms;
    uint8_t payload[PROTO_MAX_PAYLOAD_BYTES];
    size_t payload_len;
} frame_t;

/* f'yi hattaki baytlara çevirir (sondaki 0x00 dahil) ve kaç bayt olduğunu
 * döndürür. Tip bilinmiyorsa ya da yükün boyu tipe uymuyorsa 0 döner ve
 * hiçbir şey yazmaz. İmzasız mesajda (HELLO_REQ) etiket 8 × 0x00'dır. */
size_t frame_encode(const frame_t *f, const uint8_t key[FRAME_KEY_BYTES],
                    uint32_t session_id, uint8_t out[PROTO_MAX_WIRE_BYTES]);

/* Ayraçsız kodlanmış çerçeveyi çözer ve denetler. Sıra: COBS → CRC →
 * tip/yön/kanal/uzunluk → etiket. channel ve dir ALICININ bulunduğu port
 * (PROTO_CH_AGENT ya da PROTO_CH_VEHICLE) ve beklediği yöndür. FRAME_OK
 * dışında *out'a dokunulmaz. wire en fazla PROTO_MAX_WIRE_BYTES - 1 bayt
 * olabilir; frame_rx bundan uzununu zaten vermez. */
frame_result_t frame_decode(const uint8_t *wire, size_t len,
                            const uint8_t key[FRAME_KEY_BYTES], uint32_t session_id,
                            uint8_t channel, uint8_t dir, frame_t *out);

/* ---- Bayt akışını ayraçlarda bölmek -------------------------------------- */

typedef enum {
    FRAME_RX_NONE,       /* Çerçeve henüz tamamlanmadı */
    FRAME_RX_FRAME,      /* rx.buf'taki rx.len bayt, ayraçsız bir çerçeve */
    FRAME_RX_OVERFLOW,   /* Sınırı aşan bir çerçeve atıldı → err_framing */
} frame_rx_event_t;

typedef struct {
    uint8_t buf[PROTO_MAX_WIRE_BYTES];
    size_t len;
    bool overflow;   /* Sınır aşıldı, bir sonraki ayraca kadar atılıyor */
    bool handed;     /* buf son çağrıda verildi, sıradaki baytta boşaltılır */
} frame_rx_t;

void frame_rx_init(frame_rx_t *rx);

/* Bir bayt ekler. FRAME_RX_FRAME dönerse çerçeve rx->buf ve rx->len'dedir ve
 * bir sonraki frame_rx_push() çağrısına kadar geçerlidir. Art arda iki ayraç
 * (boş çerçeve) yok sayılır: gönderici senkronu tazelemek için çerçeve
 * başına da ayraç koyabilir. */
frame_rx_event_t frame_rx_push(frame_rx_t *rx, uint8_t byte);

#endif /* FRAME_H */
