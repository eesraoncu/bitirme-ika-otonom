/* SHA-256 (FIPS 180-4): her girdiyi 32 baytlık bir parmak izine çevirir.
 * İçinde sır yoktur; anahtarı işe katan HMAC'tir (hmac_sha256.h).
 *
 * Veri parça parça verilebilir: init → update (istenen kadar) → final.
 * Sonuç, veri tek parçada verilmiş gibi aynıdır. */
#ifndef SHA256_H
#define SHA256_H

#include <stddef.h>
#include <stdint.h>

#define SHA256_DIGEST_BYTES 32u
#define SHA256_BLOCK_BYTES  64u

typedef struct {
    uint32_t state[8];                  /* Karıştırılan durum, sonunda çıktı */
    uint64_t total_len;                 /* Şimdiye kadar verilen bayt */
    uint8_t block[SHA256_BLOCK_BYTES];  /* Henüz dolmamış blok */
    size_t block_len;
} sha256_ctx_t;

void sha256_init(sha256_ctx_t *ctx);
void sha256_update(sha256_ctx_t *ctx, const uint8_t *data, size_t len);

/* Doldurmayı ekler, son bloğu işler ve özeti out'a yazar. Bundan sonra ctx
 * yeniden kullanılacaksa sha256_init() çağrılmalı. */
void sha256_final(sha256_ctx_t *ctx, uint8_t out[SHA256_DIGEST_BYTES]);

#endif /* SHA256_H */
