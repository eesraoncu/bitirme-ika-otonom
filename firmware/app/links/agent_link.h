/* Ajan kanalı: LPUART1 (ST-LINK sanal seri portu, PA2/PA3), 115200 8N1.
 *
 * Alma dairesel DMA ile, gönderme normal DMA ile yapılır (K-017). Hiçbir
 * fonksiyon beklemez. Bu modül yalnızca bayt taşır, baytların ne anlama
 * geldiğine bakmaz. Çerçeveleme ve protokol bu katmanın üstündedir. */
#ifndef AGENT_LINK_H
#define AGENT_LINK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* agent_link_send()'in tek seferde kabul ettiği en fazla bayt. En uzun
 * çerçeve (VERDICT) hatta 44 bayt (docs/protocol.md §4.1). */
#define AGENT_LINK_TX_MAX 64u

/* Bir kez, MX_LPUART1_UART_Init() ve MX_DMA_Init()'ten sonra çağrılır.
 * Dairesel almayı başlatır. */
void agent_link_init(void);

/* Son çağrıdan beri gelen en fazla max baytı out'a kopyalar ve kaç bayt
 * kopyaladığını döndürür. Yeni bayt yoksa 0 döner. */
size_t agent_link_read(uint8_t *out, size_t max);

/* Önceki gönderim bittiyse true. */
bool agent_link_tx_ready(void);

/* len baytı DMA ile göndermeye başlar ve hemen döner. Veri modülün kendi
 * tamponuna kopyalanır, data dönüşten sonra yeniden kullanılabilir.
 * Önceki gönderim sürüyorsa ya da len uygun değilse false döner ve hiçbir
 * şey göndermez. */
bool agent_link_send(const uint8_t *data, size_t len);

#endif /* AGENT_LINK_H */
