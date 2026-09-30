/* Kartın çerçeveleme kodunu (firmware/app/protocol/, firmware/app/auth/) PC'de
 * çalıştıran sürücü. test_c_framer.py bunu gcc ile derler, stdin'den komut
 * yollar ve cevabı Python referansıyla karşılaştırır.
 *
 * Her satır bir komut, her komuta bir satır cevap. Boş veri "-" ile yazılır.
 *   crc <hex>               → CRC, 4 hane onaltılık
 *   cobs_enc <hex>          → kodlanmış veri
 *   cobs_dec <hex>          → çözülmüş veri; reddedilirse ERR
 *   cobs_dec4 <hex>         → cobs_dec gibi, ama çıkış tamponu 4 bayt
 *   sha256 <parçalar>       → özet
 *   sha256_rep <bayt> <n>   → n tane aynı bayttan oluşan verinin özeti
 *   hmac <anahtar> <parçalar> → HMAC-SHA256
 *   tag_eq <hex> <hex>      → hmac_tag_equal sonucu, 1 ya da 0
 * <parçalar> noktayla bölünmüş onaltılık metindir ("aabb.cc"). Her parça ayrı
 * bir update çağrısıyla verilir: blok sınırı hataları böyle yakalanır. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "auth/hmac_sha256.h"
#include "auth/sha256.h"
#include "protocol/cobs.h"
#include "protocol/crc16.h"

#define BUF_MAX    1024u
#define CHUNKS_MAX 64u
#define ARGS_MAX   3u

static int nibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/* "aabb.cc" gibi noktayla bölünmüş onaltılık metni out'a çevirir. Her
 * parçanın bittiği konumu ends'e yazar. Parça sayısını döndürür; geçersiz
 * metinde ya da sığmıyorsa -1. "-" boş veridir (tek, boş parça). */
static int parse_chunks(const char *s, uint8_t *out, size_t max, size_t *ends)
{
    size_t n = 0;
    unsigned count = 0;
    if (strcmp(s, "-") == 0) {
        ends[0] = 0;
        return 1;
    }
    for (;;) {
        size_t len = strcspn(s, ".");
        if (len % 2u != 0u || n + len / 2u > max || count == CHUNKS_MAX) {
            return -1;
        }
        for (size_t i = 0; i < len; i += 2u) {
            int hi = nibble(s[i]);
            int lo = nibble(s[i + 1u]);
            if (hi < 0 || lo < 0) {
                return -1;
            }
            out[n++] = (uint8_t)(hi << 4 | lo);
        }
        ends[count++] = n;
        if (s[len] == '\0') {
            return (int)count;
        }
        s += len + 1u;
    }
}

/* Tek parçalı onaltılık metin. Başarılıysa true ve bayt sayısı *n'de. */
static bool parse_hex(const char *s, uint8_t *out, size_t max, size_t *n)
{
    size_t ends[CHUNKS_MAX];
    if (parse_chunks(s, out, max, ends) != 1) {
        return false;
    }
    *n = ends[0];
    return true;
}

static void print_hex(const uint8_t *b, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        printf("%02x", (unsigned)b[i]);
    }
    printf("\n");
}

/* Bir komutu çalıştırır. Girdisi geçersizse false döner. */
static bool run(const char *cmd, char *const *arg, unsigned argc)
{
    static uint8_t in[BUF_MAX];
    static uint8_t in2[BUF_MAX];
    static uint8_t out[COBS_ENCODED_MAX(BUF_MAX)];
    size_t ends[CHUNKS_MAX];
    size_t n;
    size_t n2;

    if (strcmp(cmd, "crc") == 0 && argc == 1u) {
        if (!parse_hex(arg[0], in, BUF_MAX, &n)) return false;
        printf("%04x\n", (unsigned)crc16_ccitt_false(in, n));
    } else if (strcmp(cmd, "cobs_enc") == 0 && argc == 1u) {
        if (!parse_hex(arg[0], in, BUF_MAX, &n)) return false;
        print_hex(out, cobs_encode(in, n, out));
    } else if ((strcmp(cmd, "cobs_dec") == 0 || strcmp(cmd, "cobs_dec4") == 0) && argc == 1u) {
        if (!parse_hex(arg[0], in, BUF_MAX, &n)) return false;
        size_t max = strcmp(cmd, "cobs_dec4") == 0 ? 4u : sizeof out;
        if (cobs_decode(in, n, out, max, &n2)) {
            print_hex(out, n2);
        } else {
            printf("ERR\n");
        }
    } else if (strcmp(cmd, "sha256") == 0 && argc == 1u) {
        int count = parse_chunks(arg[0], in, BUF_MAX, ends);
        if (count < 0) return false;
        sha256_ctx_t c;
        sha256_init(&c);
        size_t start = 0;
        for (int k = 0; k < count; k++) {
            sha256_update(&c, &in[start], ends[k] - start);
            start = ends[k];
        }
        sha256_final(&c, out);
        print_hex(out, SHA256_DIGEST_BYTES);
    } else if (strcmp(cmd, "sha256_rep") == 0 && argc == 2u) {
        if (!parse_hex(arg[0], in2, 1u, &n2) || n2 != 1u) return false;
        unsigned long total = strtoul(arg[1], NULL, 10);
        memset(in, in2[0], BUF_MAX);
        sha256_ctx_t c;
        sha256_init(&c);
        /* Değişen boylarda parçalar: blok sınırı her yere denk gelsin. */
        size_t step = 1;
        while (total > 0u) {
            size_t take = step < total ? step : (size_t)total;
            sha256_update(&c, in, take);
            total -= take;
            step = step % 200u + 7u;
        }
        sha256_final(&c, out);
        print_hex(out, SHA256_DIGEST_BYTES);
    } else if (strcmp(cmd, "hmac") == 0 && argc == 2u) {
        if (!parse_hex(arg[0], in2, BUF_MAX, &n2)) return false;
        int count = parse_chunks(arg[1], in, BUF_MAX, ends);
        if (count < 0) return false;
        hmac_sha256_ctx_t c;
        hmac_sha256_init(&c, in2, n2);
        size_t start = 0;
        for (int k = 0; k < count; k++) {
            hmac_sha256_update(&c, &in[start], ends[k] - start);
            start = ends[k];
        }
        hmac_sha256_final(&c, out);
        print_hex(out, SHA256_DIGEST_BYTES);
    } else if (strcmp(cmd, "tag_eq") == 0 && argc == 2u) {
        if (!parse_hex(arg[0], in, BUF_MAX, &n) || !parse_hex(arg[1], in2, BUF_MAX, &n2) ||
            n != n2) {
            return false;
        }
        printf("%d\n", hmac_tag_equal(in, in2, n) ? 1 : 0);
    } else {
        return false;
    }
    return true;
}

int main(void)
{
    static char line[8u * BUF_MAX];

    while (fgets(line, sizeof line, stdin) != NULL) {
        line[strcspn(line, "\r\n")] = '\0';

        /* Boşlukla ayrılmış: komut ve en fazla ARGS_MAX argüman. */
        char *arg[ARGS_MAX + 1u];
        unsigned argc = 0;
        char *cmd = line;
        char *p = strchr(line, ' ');
        while (p != NULL && argc <= ARGS_MAX) {
            *p++ = '\0';
            arg[argc++] = p;
            p = strchr(p, ' ');
        }
        if (argc > ARGS_MAX || !run(cmd, arg, argc)) {
            printf("BAD_INPUT\n");
        }
        fflush(stdout);
    }
    return 0;
}
