#include "protocol/cobs.h"

size_t cobs_encode(const uint8_t *in, size_t len, uint8_t *out)
{
    /* Açık bloğun kod baytı, blok bitince (bir 0x00 ya da 254 bayt) geriye
     * dönüp yazılır. code = bloktaki bayt sayısı + 1. */
    size_t code_at = 0;
    size_t o = 1;
    uint8_t code = 1;

    for (size_t i = 0; i < len; i++) {
        if (in[i] == 0u) {
            out[code_at] = code;
            code_at = o++;
            code = 1;
        } else {
            out[o++] = in[i];
            code++;
            if (code == 0xFFu) {   /* 254 sıfırsız bayt: blok dolu */
                out[code_at] = code;
                if (i == len - 1u) {
                    return o;      /* Kanonik biçim: sona ek kod yok */
                }
                code_at = o++;
                code = 1;
            }
        }
    }
    out[code_at] = code;
    return o;
}

bool cobs_decode(const uint8_t *in, size_t len, uint8_t *out, size_t out_max,
                 size_t *out_len)
{
    if (len == 0u) {
        return false;
    }

    size_t i = 0;
    size_t o = 0;
    while (i < len) {
        uint8_t code = in[i++];
        if (code == 0u) {
            return false;
        }
        size_t end = i + (size_t)code - 1u;   /* Bloğun son baytından sonrası */
        if (end > len || end - i > out_max - o) {
            return false;
        }
        while (i < end) {
            if (in[i] == 0u) {
                return false;
            }
            out[o++] = in[i++];
        }
        /* 0xFF dolu bir bloktur, arkasında sıfır yoktu. Son bloğun
         * arkasında da sıfır yok: orada veri bitiyor. */
        if (code != 0xFFu && i < len) {
            if (o == out_max) {
                return false;
            }
            out[o++] = 0u;
        }
    }
    *out_len = o;
    return true;
}
