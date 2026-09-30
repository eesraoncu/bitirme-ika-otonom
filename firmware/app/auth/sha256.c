#include "auth/sha256.h"

#include <string.h>

/* Tur sabitleri: ilk 64 asal sayının küpkökünün kesirli kısmının ilk 32 biti.
 * Keyfi değil, türetilebilir sayılar: içlerine bir arka kapı gizlenmediği
 * görülsün diye böyle seçilmişler. */
static const uint32_t K[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
    0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
    0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
    0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u,
};

static uint32_t rotr(uint32_t x, unsigned n)
{
    return (x >> n) | (x << (32u - n));
}

/* Bir 64 baytlık bloğu duruma karıştırır (FIPS 180-4 §6.2.2). */
static void compress(uint32_t state[8], const uint8_t block[SHA256_BLOCK_BYTES])
{
    /* 1. Blok 16 kelimeden 64 kelimeye genişletilir. SHA-256 sayıları büyük
     *    uçtan okur; Cortex-M4 küçük uçtan çalıştığı için bayt bayt kurulur. */
    uint32_t w[64];
    for (unsigned t = 0; t < 16u; t++) {
        w[t] = (uint32_t)block[4u * t] << 24 | (uint32_t)block[4u * t + 1u] << 16 |
               (uint32_t)block[4u * t + 2u] << 8 | (uint32_t)block[4u * t + 3u];
    }
    for (unsigned t = 16; t < 64u; t++) {
        uint32_t s0 = rotr(w[t - 15u], 7) ^ rotr(w[t - 15u], 18) ^ (w[t - 15u] >> 3);
        uint32_t s1 = rotr(w[t - 2u], 17) ^ rotr(w[t - 2u], 19) ^ (w[t - 2u] >> 10);
        w[t] = w[t - 16u] + s0 + w[t - 7u] + s1;
    }

    /* 2. Durumun kopyası 64 tur karıştırılır. Toplamalar 2^32'ye göre:
     *    uint32_t taşınca kendiliğinden başa döner. */
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
    uint32_t e = state[4], f = state[5], g = state[6], h = state[7];
    for (unsigned t = 0; t < 64u; t++) {
        uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        uint32_t ch = (e & f) ^ (~e & g);          /* e'nin biti f mi g mi seçer */
        uint32_t t1 = h + S1 + ch + K[t] + w[t];
        uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        uint32_t maj = (a & b) ^ (a & c) ^ (b & c); /* üçünün çoğunluğu */
        uint32_t t2 = S0 + maj;
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    /* 3. Karışan sonuç duruma eklenir. */
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

void sha256_init(sha256_ctx_t *ctx)
{
    /* Başlangıç durumu: ilk 8 asalın karekökünün kesirli kısmı. */
    static const uint32_t H0[8] = {
        0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
        0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u,
    };
    memcpy(ctx->state, H0, sizeof H0);
    ctx->total_len = 0;
    ctx->block_len = 0;
}

void sha256_update(sha256_ctx_t *ctx, const uint8_t *data, size_t len)
{
    ctx->total_len += len;
    while (len > 0u) {
        size_t take = SHA256_BLOCK_BYTES - ctx->block_len;
        if (take > len) {
            take = len;
        }
        memcpy(&ctx->block[ctx->block_len], data, take);
        ctx->block_len += take;
        data += take;
        len -= take;
        if (ctx->block_len == SHA256_BLOCK_BYTES) {
            compress(ctx->state, ctx->block);
            ctx->block_len = 0;
        }
    }
}

void sha256_final(sha256_ctx_t *ctx, uint8_t out[SHA256_DIGEST_BYTES])
{
    /* Doldurma: 0x80, sıfırlar, en sonda 8 bayt bit cinsinden uzunluk.
     * Uzunluğa yer kalmadıysa (56 bayttan fazla dolu) bir blok daha gerekir. */
    uint64_t bits = ctx->total_len * 8u;
    ctx->block[ctx->block_len++] = 0x80u;
    if (ctx->block_len > SHA256_BLOCK_BYTES - 8u) {
        memset(&ctx->block[ctx->block_len], 0, SHA256_BLOCK_BYTES - ctx->block_len);
        compress(ctx->state, ctx->block);
        ctx->block_len = 0;
    }
    memset(&ctx->block[ctx->block_len], 0, SHA256_BLOCK_BYTES - 8u - ctx->block_len);
    for (unsigned i = 0; i < 8u; i++) {
        ctx->block[SHA256_BLOCK_BYTES - 8u + i] = (uint8_t)(bits >> (56u - 8u * i));
    }
    compress(ctx->state, ctx->block);

    /* Çıktı da büyük uçtan yazılır. */
    for (unsigned i = 0; i < 8u; i++) {
        out[4u * i]      = (uint8_t)(ctx->state[i] >> 24);
        out[4u * i + 1u] = (uint8_t)(ctx->state[i] >> 16);
        out[4u * i + 2u] = (uint8_t)(ctx->state[i] >> 8);
        out[4u * i + 3u] = (uint8_t)ctx->state[i];
    }
}
