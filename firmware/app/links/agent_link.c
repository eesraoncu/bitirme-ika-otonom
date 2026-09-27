#include "links/agent_link.h"

#include <string.h>

#include "usart.h"   /* hlpuart1 (CubeMX), HAL, Error_Handler() */

/* Dairesel alma tamponu. Hat tam doluyken 256 bayt yaklaşık 22 ms eder.
 * agent_link_read() bundan seyrek çağrılırsa DMA okunmamış baytların
 * üstüne yazar ve bu fark edilemez. app_loop() mikrosaniyeler içinde
 * döndüğü için pay büyük. */
#define RX_SIZE 256u

static uint8_t rx_buf[RX_SIZE];
static size_t rx_tail;   /* Bir sonraki okunacak konum */

/* DMA gönderim bitene kadar buradan okur. Çağıranın dizisi yerine buraya
 * kopyalandığı için "gönderim bitmeden diziyi değiştirme" kuralı modülün
 * dışına taşmaz. */
static uint8_t tx_buf[AGENT_LINK_TX_MAX];

/* Almanın hat hatası yüzünden kaç kez yeniden başlatıldığı. Şimdilik
 * yalnızca hata ayıklayıcıdan okunur. */
static uint32_t rx_restarts;

static void rx_start(void)
{
    rx_tail = 0;
    if (HAL_UART_Receive_DMA(&hlpuart1, rx_buf, RX_SIZE) != HAL_OK) {
        Error_Handler();
    }
}

void agent_link_init(void)
{
    rx_start();
}

size_t agent_link_read(uint8_t *out, size_t max)
{
    /* Taşma (overrun) gibi bir hat hatasında HAL almayı durdurur ve
     * RxState'i READY'ye çeker. Kendiliğinden yeniden başlamaz. */
    if (hlpuart1.RxState != HAL_UART_STATE_BUSY_RX) {
        rx_restarts++;
        rx_start();
        return 0;
    }

    /* DMA'nın bir sonraki yazacağı konum. Sayaç, tamponun sonuna kadar
     * kalan bayt sayısını tutar. */
    size_t head = RX_SIZE - __HAL_DMA_GET_COUNTER(hlpuart1.hdmarx);
    if (head == RX_SIZE) {   /* Sayaç başa dönerken 0 okunursa */
        head = 0;
    }
    /* Tampondaki baytlar sayaçtan sonra okunmalı. Derleyici bu sırayı
     * değiştiremesin. */
    __DMB();

    size_t n = 0;
    while (rx_tail != head && n < max) {
        out[n++] = rx_buf[rx_tail];
        rx_tail = (rx_tail + 1u) % RX_SIZE;
    }
    return n;
}

bool agent_link_tx_ready(void)
{
    /* HAL, gönderim bitince LPUART1 kesmesinde gState'i READY yapar. */
    return hlpuart1.gState == HAL_UART_STATE_READY;
}

bool agent_link_send(const uint8_t *data, size_t len)
{
    if (len == 0u || len > AGENT_LINK_TX_MAX || !agent_link_tx_ready()) {
        return false;
    }
    memcpy(tx_buf, data, len);
    return HAL_UART_Transmit_DMA(&hlpuart1, tx_buf, (uint16_t)len) == HAL_OK;
}
