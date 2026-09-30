/* Kartın çerçeveleme kodunu (firmware/app/protocol/) PC'de çalıştıran sürücü.
 * test_c_framer.py bunu gcc ile derler, stdin'den komut yollar ve cevabı
 * Python referansıyla karşılaştırır.
 *
 * Her satır bir komut, her komuta bir satır cevap:
 *   crc <hex>       → CRC, 4 hane onaltılık
 *   cobs_enc <hex>  → kodlanmış veri, onaltılık
 *   cobs_dec <hex>  → çözülmüş veri, onaltılık; reddedilirse ERR
 *   cobs_dec4 <hex> → cobs_dec gibi, ama çıkış tamponu 4 bayt (taşma denetimi)
 * Boş veri için hex kısmı yazılmaz. */
#include <stdio.h>
#include <string.h>

#include "protocol/cobs.h"
#include "protocol/crc16.h"

#define BUF_MAX 1024u

static int nibble(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/* Onaltılık metni bayta çevirir. Geçersizse ya da sığmıyorsa -1 döner. */
static long parse_hex(const char *s, uint8_t *out, size_t max)
{
    size_t n = strlen(s);
    if (n % 2u != 0u || n / 2u > max) {
        return -1;
    }
    for (size_t i = 0; i < n / 2u; i++) {
        int hi = nibble(s[2u * i]);
        int lo = nibble(s[2u * i + 1u]);
        if (hi < 0 || lo < 0) {
            return -1;
        }
        out[i] = (uint8_t)(hi << 4 | lo);
    }
    return (long)(n / 2u);
}

static void print_hex(const uint8_t *b, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        printf("%02x", (unsigned)b[i]);
    }
    printf("\n");
}

int main(void)
{
    static char line[4u * BUF_MAX];
    static uint8_t in[BUF_MAX];
    static uint8_t out[COBS_ENCODED_MAX(BUF_MAX)];

    while (fgets(line, sizeof line, stdin) != NULL) {
        line[strcspn(line, "\r\n")] = '\0';
        char *arg = strchr(line, ' ');
        if (arg != NULL) {
            *arg++ = '\0';
        } else {
            arg = line + strlen(line);   /* Boş veri */
        }
        long parsed = parse_hex(arg, in, BUF_MAX);
        if (parsed < 0) {
            printf("BAD_INPUT\n");
            continue;
        }
        size_t n = (size_t)parsed;

        if (strcmp(line, "crc") == 0) {
            printf("%04x\n", (unsigned)crc16_ccitt_false(in, n));
        } else if (strcmp(line, "cobs_enc") == 0) {
            print_hex(out, cobs_encode(in, n, out));
        } else if (strcmp(line, "cobs_dec") == 0 || strcmp(line, "cobs_dec4") == 0) {
            size_t max = strcmp(line, "cobs_dec4") == 0 ? 4u : sizeof out;
            size_t m;
            if (cobs_decode(in, n, out, max, &m)) {
                print_hex(out, m);
            } else {
                printf("ERR\n");
            }
        } else {
            printf("BAD_COMMAND\n");
        }
        fflush(stdout);
    }
    return 0;
}
