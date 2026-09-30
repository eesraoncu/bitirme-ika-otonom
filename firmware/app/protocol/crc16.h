/* CRC-16/CCITT-FALSE: çerçevenin yolda bozulup bozulmadığını sorar
 * (docs/protocol.md §4.3). Kazaya karşı korur, kasta karşı korumaz: formül
 * herkese açık. Kasta karşı koruyan HMAC'tir (app/auth/).
 *
 * Bölen 0x1021, başlangıç 0xFFFF, yansıtmasız, son XOR yok.
 * Bilinen cevap: "123456789" → 0x29B1. */
#ifndef CRC16_H
#define CRC16_H

#include <stddef.h>
#include <stdint.h>

uint16_t crc16_ccitt_false(const uint8_t *data, size_t len);

#endif /* CRC16_H */
