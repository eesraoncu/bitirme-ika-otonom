#include "app.h"

#include "main.h"   /* HAL (HAL_GetTick) ve BSP (BSP_LED_*) */

/* Faz 2.1 doğrulaması: kısa bir "nabız". Saniyede bir, 100 ms yanık.
 * LED testinin 500/500 deseninden gözle ayırt edilsin diye farklı seçildi.
 * LED bu desenle yanıp sönüyorsa HSE kristali başlamış ve PLL 170 MHz'e
 * kilitlenmiş demektir. Aksi hâlde SystemClock_Config() hata verir ve
 * program Error_Handler()'da takılırdı. */
#define PULSE_PERIOD_MS 1000u
#define PULSE_ON_MS      100u

void app_init(void)
{
    /* Faz 2.2'de ajan kanalının başlatılması buraya gelecek. */
}

void app_loop(void)
{
    if (HAL_GetTick() % PULSE_PERIOD_MS < PULSE_ON_MS) {
        BSP_LED_On(LED_GREEN);
    } else {
        BSP_LED_Off(LED_GREEN);
    }
}
