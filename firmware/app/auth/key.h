/* HMAC anahtarı (docs/protocol.md §11).
 *
 * Anahtar depoda değil, secrets/hmac_key.bin'de durur (K-007). Kart onu
 * tools/gen_key.py'nin ürettiği secrets/hmac_key.h'den derleme sırasında
 * alır. Başlık yoksa derleme durur: kart anahtarsız ya da test anahtarıyla
 * derlenemez.
 *
 * Anahtar flash'ta durur. Okuma koruması (RDP) açık değil: kartın ST-LINK'ine
 * erişen biri anahtarı okuyabilir. */
#ifndef KEY_H
#define KEY_H

#include <stdint.h>

#include "protocol/frame.h"   /* FRAME_KEY_BYTES */

extern const uint8_t auth_key[FRAME_KEY_BYTES];

#endif /* KEY_H */
