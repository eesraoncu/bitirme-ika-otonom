/* HMAC-SHA256 (RFC 2104): anahtarı bilmeyenin üretemeyeceği parmak izi.
 *
 *   HMAC(K, m) = SHA-256( (K ⊕ opad) ‖ SHA-256( (K ⊕ ipad) ‖ m ) )
 *
 * SHA-256(K ‖ m) yeterli olmazdı: SHA-256'nın çıktısı iç durumun kendisi
 * olduğu için saldırgan anahtarı bilmeden m'nin sonuna ekleme yapıp geçerli
 * bir özet üretebilirdi (uzunluk uzatma). Dıştaki ikinci özet bunu kapatır.
 *
 * Çerçevede: etiket = HMAC(anahtar, session_id ‖ başlık ‖ yük)[0:8]
 * (docs/protocol.md §4.5, §5.2). */
#ifndef HMAC_SHA256_H
#define HMAC_SHA256_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "auth/sha256.h"

typedef struct {
    sha256_ctx_t inner;   /* (K ⊕ ipad) ‖ m */
    sha256_ctx_t outer;   /* (K ⊕ opad) ‖ iç özet */
} hmac_sha256_ctx_t;

/* Anahtarı hazırlar. 64 bayttan uzun anahtarın önce kendi özeti alınır
 * (RFC 2104); bizim anahtarımız 32 bayt. */
void hmac_sha256_init(hmac_sha256_ctx_t *ctx, const uint8_t *key, size_t key_len);
void hmac_sha256_update(hmac_sha256_ctx_t *ctx, const uint8_t *data, size_t len);
void hmac_sha256_final(hmac_sha256_ctx_t *ctx, uint8_t out[SHA256_DIGEST_BYTES]);

/* a ile b'nin ilk len baytı aynıysa true. Süre, nerede fark olduğuna bağlı
 * değildir: memcmp ilk farkta durur ve cevap süresinden etiketin kaç baytının
 * doğru olduğu sızar (docs/protocol.md §4.5). */
bool hmac_tag_equal(const uint8_t *a, const uint8_t *b, size_t len);

#endif /* HMAC_SHA256_H */
