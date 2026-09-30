/* Seri kanallar, ikisi de 115200 8N1:
 *   ajan kanalı: LPUART1 (ST-LINK sanal seri portu, PA2/PA3)
 *   araç kanalı: USART1 (CP2102 modülü, PC4/PC5, kartta D1/D0)
 *
 * Alma dairesel DMA ile, gönderme normal DMA ile yapılır (K-017, K-018).
 * Hiçbir fonksiyon beklemez. Bu modül yalnızca bayt taşır, baytların ne
 * anlama geldiğine bakmaz. Çerçeveleme ve protokol bu katmanın üstündedir.
 * Her fonksiyon hangi kanalın kastedildiğini port parametresinden alır.
 * Çağıran her baytın hangi porttan geldiğini bilir (porta göre güven,
 * docs/protocol.md). */
#ifndef SERIAL_LINK_H
#define SERIAL_LINK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* serial_link_send()'in tek seferde kabul ettiği en fazla bayt. En uzun
 * çerçeve (VERDICT) hatta 44 bayt (docs/protocol.md §4.1). */
#define SERIAL_LINK_TX_MAX 64u

typedef enum {
    SERIAL_LINK_AGENT,     /* LPUART1, ST-LINK kablosu */
    SERIAL_LINK_VEHICLE,   /* USART1, CP2102 modülü */
} serial_link_port_t;

/* Bir kez, MX_DMA_Init(), MX_LPUART1_UART_Init() ve MX_USART1_UART_Init()'ten
 * sonra çağrılır. İki kanalda da dairesel almayı başlatır. */
void serial_link_init(void);

/* Son çağrıdan beri port'tan gelen en fazla max baytı out'a kopyalar ve kaç
 * bayt kopyaladığını döndürür. Yeni bayt yoksa 0 döner. */
size_t serial_link_read(serial_link_port_t port, uint8_t *out, size_t max);

/* port'taki önceki gönderim bittiyse true. */
bool serial_link_tx_ready(serial_link_port_t port);

/* len baytı port'tan DMA ile göndermeye başlar ve hemen döner. Veri kanalın
 * kendi tamponuna kopyalanır, data dönüşten sonra yeniden kullanılabilir.
 * Önceki gönderim sürüyorsa ya da len uygun değilse false döner ve hiçbir
 * şey göndermez. */
bool serial_link_send(serial_link_port_t port, const uint8_t *data, size_t len);

#endif /* SERIAL_LINK_H */
