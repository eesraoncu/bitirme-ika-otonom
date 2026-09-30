#include "auth/hmac_sha256.h"

#include <string.h>

#define IPAD 0x36u
#define OPAD 0x5Cu

void hmac_sha256_init(hmac_sha256_ctx_t *ctx, const uint8_t *key, size_t key_len)
{
    /* Anahtar 64 bayta sıfırla tamamlanır. */
    uint8_t k[SHA256_BLOCK_BYTES] = {0};
    if (key_len > SHA256_BLOCK_BYTES) {
        sha256_ctx_t h;
        sha256_init(&h);
        sha256_update(&h, key, key_len);
        sha256_final(&h, k);
    } else {
        memcpy(k, key, key_len);
    }

    /* İki maskeyle iki farklı anahtar türetilir. Dış özet de burada
     * başlatılır: böylece hazırlanmış bir ctx kopyalanıp her çerçevede
     * yeniden kullanılabilir. */
    uint8_t pad[SHA256_BLOCK_BYTES];
    for (unsigned i = 0; i < SHA256_BLOCK_BYTES; i++) {
        pad[i] = (uint8_t)(k[i] ^ IPAD);
    }
    sha256_init(&ctx->inner);
    sha256_update(&ctx->inner, pad, sizeof pad);

    for (unsigned i = 0; i < SHA256_BLOCK_BYTES; i++) {
        pad[i] = (uint8_t)(k[i] ^ OPAD);
    }
    sha256_init(&ctx->outer);
    sha256_update(&ctx->outer, pad, sizeof pad);
}

void hmac_sha256_update(hmac_sha256_ctx_t *ctx, const uint8_t *data, size_t len)
{
    sha256_update(&ctx->inner, data, len);
}

void hmac_sha256_final(hmac_sha256_ctx_t *ctx, uint8_t out[SHA256_DIGEST_BYTES])
{
    uint8_t inner_digest[SHA256_DIGEST_BYTES];
    sha256_final(&ctx->inner, inner_digest);
    sha256_update(&ctx->outer, inner_digest, sizeof inner_digest);
    sha256_final(&ctx->outer, out);
}

bool hmac_tag_equal(const uint8_t *a, const uint8_t *b, size_t len)
{
    /* Farklar biriktirilir, karar en sonda verilir: her zaman len tur. */
    uint8_t diff = 0;
    for (size_t i = 0; i < len; i++) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}
