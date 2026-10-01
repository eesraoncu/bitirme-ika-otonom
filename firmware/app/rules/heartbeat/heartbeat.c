#include "rules/heartbeat/heartbeat.h"

#include "tim.h"   /* CubeMX: htim6 */

/* Kesme ile ana döngü arasında paylaşılır. */
static volatile bool alive;
static volatile bool lost;

/* Bağlantı canlıyken zaman aşımı oldu. Kesmede ya da heartbeat_feed()'de,
 * kesmeler kapalıyken çağrılır. */
static void expire(void)
{
    if (alive) {
        alive = false;
        lost = true;
    }
}

void heartbeat_init(void)
{
    alive = false;
    lost = false;
    /* HAL_TIM_Base_Init sayacı yüklemek için bir güncelleme olayı üretir.
     * Bu HAL sürümü o sırada güncelleme bayrağını kurmuyor (URS), eski
     * sürümler kuruyordu: zamanlayıcı başlar başlamaz sahte bir zaman aşımı
     * gelirdi. HAL'in davranışına güvenmeden temizlenir. */
    __HAL_TIM_CLEAR_FLAG(&htim6, TIM_FLAG_UPDATE);
    (void)HAL_TIM_Base_Start_IT(&htim6);
}

void heartbeat_feed(void)
{
    __disable_irq();
    /* Sayaç tam bu arada taştıysa kesme bekliyordur. Önce o işlenir: 500 ms
     * gerçekten geçti, bağlantı bir kez ölmüş sayılır (HOLD mandallıdır,
     * docs/RULES.md §5.2). Sonra yeni kalp atışı bağlantıyı canlandırır. */
    if (__HAL_TIM_GET_FLAG(&htim6, TIM_FLAG_UPDATE)) {
        __HAL_TIM_CLEAR_FLAG(&htim6, TIM_FLAG_UPDATE);
        expire();
    }
    __HAL_TIM_SET_COUNTER(&htim6, 0u);
    alive = true;
    __enable_irq();
}

bool heartbeat_alive(void)
{
    return alive;
}

bool heartbeat_take_lost(void)
{
    __disable_irq();
    bool was = lost;
    lost = false;
    __enable_irq();
    return was;
}

/* HAL'in zayıf (weak) geri çağrısı: TIM6 taşınca HAL_TIM_IRQHandler çağırır.
 * Projede bu geri çağrıyı kullanan tek zamanlayıcı TIM6. Başka bir
 * zamanlayıcı eklenirse buradan ayrıştırılmalı. */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM6) {
        expire();
    }
}
