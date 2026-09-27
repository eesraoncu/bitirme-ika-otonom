#include "app.h"

#include "main.h"   /* HAL (HAL_GetTick) ve BSP (BSP_LED_*) */
#include "links/agent_link.h"

/* Faz 2.1 doğrulaması: kısa bir "nabız". Saniyede bir, 100 ms yanık.
 * LED testinin 500/500 deseninden gözle ayırt edilsin diye farklı seçildi.
 * LED bu desenle yanıp sönüyorsa HSE kristali başlamış ve PLL 170 MHz'e
 * kilitlenmiş demektir. Aksi hâlde SystemClock_Config() hata verir ve
 * program Error_Handler()'da takılırdı. Nabız sürdükçe app_loop()'un
 * takılmadığı da görülür. */
#define PULSE_PERIOD_MS 1000u
#define PULSE_ON_MS      100u

void app_init(void)
{
    agent_link_init();
}

void app_loop(void)
{
    /* Faz 2.2 yankı testi: gelen her baytı geri gönder. Gönderme meşgulken
     * okunmaz, baytlar dairesel tamponda bekler. Faz 2.6'da baytlar burada
     * çerçeveleyiciye verilecek. */
    if (agent_link_tx_ready()) {
        uint8_t buf[AGENT_LINK_TX_MAX];
        size_t n = agent_link_read(buf, sizeof buf);
        if (n > 0u) {
            (void)agent_link_send(buf, n);
        }
    }

    if (HAL_GetTick() % PULSE_PERIOD_MS < PULSE_ON_MS) {
        BSP_LED_On(LED_GREEN);
    } else {
        BSP_LED_Off(LED_GREEN);
    }
}
