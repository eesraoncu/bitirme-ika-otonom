#include "protocol/crc16.h"

uint16_t crc16_ccitt_false(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; i++) {
        /* Yeni baytı üst 8 bite kat, sonra bitleri soldan teker teker dışarı
         * it. Dışarı 1 düşerse böleni XOR'la "çıkar". Elde kalan, bölümden
         * kalandır. */
        crc ^= (uint16_t)(data[i] << 8);
        for (int bit = 0; bit < 8; bit++) {
            if (crc & 0x8000u) {
                crc = (uint16_t)((crc << 1) ^ 0x1021u);
            } else {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}
