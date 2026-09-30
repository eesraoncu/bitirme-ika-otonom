#include "links/serial_link.h"

#include <string.h>

#include "usart.h"   /* hlpuart1, huart1 (CubeMX), HAL, Error_Handler() */

/* Dairesel alma tamponu. Hat tam doluyken 256 bayt yaklaşık 22 ms eder.
 * serial_link_read() bundan seyrek çağrılırsa DMA okunmamış baytların
 * üstüne yazar ve bu fark edilemez. app_loop() mikrosaniyeler içinde
 * döndüğü için pay büyük. */
#define RX_SIZE 256u

/* Bir kanalın bütün durumu. Her port için bir tane. */
typedef struct {
    UART_HandleTypeDef *uart;

    uint8_t rx_buf[RX_SIZE];
    size_t rx_tail;   /* Bir sonraki okunacak konum */

    /* DMA gönderim bitene kadar buradan okur. Çağıranın dizisi yerine
     * buraya kopyalandığı için "gönderim bitmeden diziyi değiştirme"
     * kuralı modülün dışına taşmaz. */
    uint8_t tx_buf[SERIAL_LINK_TX_MAX];

    /* Almanın hat hatası yüzünden kaç kez yeniden başlatıldığı. Şimdilik
     * yalnızca hata ayıklayıcıdan okunur. */
    uint32_t rx_restarts;
} channel_t;

/* Başlangıç değeri verilmedi: verilseydi tamponlarıyla birlikte .data'ya
 * girer, flash'ta yer kaplar ve her açılışta flash'tan kopyalanırdı. uart
 * serial_link_init()'te atanır. */
static channel_t agent;
static channel_t vehicle;

static channel_t *channel(serial_link_port_t port)
{
    return port == SERIAL_LINK_AGENT ? &agent : &vehicle;
}

static void rx_start(channel_t *c)
{
    c->rx_tail = 0;
    if (HAL_UART_Receive_DMA(c->uart, c->rx_buf, RX_SIZE) != HAL_OK) {
        Error_Handler();
    }
}

void serial_link_init(void)
{
    agent.uart   = &hlpuart1;
    vehicle.uart = &huart1;
    rx_start(&agent);
    rx_start(&vehicle);
}

size_t serial_link_read(serial_link_port_t port, uint8_t *out, size_t max)
{
    channel_t *c = channel(port);

    /* Taşma (overrun) gibi bir hat hatasında HAL almayı durdurur ve
     * RxState'i READY'ye çeker. Kendiliğinden yeniden başlamaz. */
    if (c->uart->RxState != HAL_UART_STATE_BUSY_RX) {
        c->rx_restarts++;
        rx_start(c);
        return 0;
    }

    /* DMA'nın bir sonraki yazacağı konum. Sayaç, tamponun sonuna kadar
     * kalan bayt sayısını tutar. */
    size_t head = RX_SIZE - __HAL_DMA_GET_COUNTER(c->uart->hdmarx);
    if (head == RX_SIZE) {   /* Sayaç başa dönerken 0 okunursa */
        head = 0;
    }
    /* Tampondaki baytlar sayaçtan sonra okunmalı. Derleyici bu sırayı
     * değiştiremesin. */
    __DMB();

    size_t n = 0;
    while (c->rx_tail != head && n < max) {
        out[n++] = c->rx_buf[c->rx_tail];
        c->rx_tail = (c->rx_tail + 1u) % RX_SIZE;
    }
    return n;
}

bool serial_link_tx_ready(serial_link_port_t port)
{
    /* HAL, gönderim bitince UART kesmesinde gState'i READY yapar. */
    return channel(port)->uart->gState == HAL_UART_STATE_READY;
}

bool serial_link_send(serial_link_port_t port, const uint8_t *data, size_t len)
{
    if (len == 0u || len > SERIAL_LINK_TX_MAX || !serial_link_tx_ready(port)) {
        return false;
    }
    channel_t *c = channel(port);
    memcpy(c->tx_buf, data, len);
    return HAL_UART_Transmit_DMA(c->uart, c->tx_buf, (uint16_t)len) == HAL_OK;
}
