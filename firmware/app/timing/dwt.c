#include "timing/dwt.h"

void dwt_init(void)
{
    /* TRCENA, DWT ve ITM birimlerinin saatini açar. Kapalıyken DWT
     * yazmaçlarına yazılan değer tutmaz (ARMv7-M kılavuzu, DEMCR). */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0u;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}
