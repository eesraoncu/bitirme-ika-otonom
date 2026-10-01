/* Karar süresi ölçümü (K-009): PA8 (TIMING) pini ve DWT çevrim sayacı.
 *
 * Pin, bir çerçevenin işlenmesi boyunca 1'dir: çerçevenin son baytı (ayraç)
 * geldiği anda 1, karar çıktıları (VERDICT, CAN mesajı) kuyruğa girdiğinde
 * 0. Mantık analizörü bağlanırsa (K-009) her çerçeve bir darbe olarak görünür.
 * DWT aynı aralığı yazılımın içinden ölçer ve istatistiği RAM'de tutar. */
#ifndef TIMING_H
#define TIMING_H

#include <stdint.h>

#include "main.h"          /* TIMING_Pin, TIMING_GPIO_Port (CubeMX) */
#include "timing/dwt.h"

typedef struct {
    uint32_t count;
    uint32_t last;   /* çevrim, 170 MHz'de 5,9 ns */
    uint32_t min;
    uint32_t max;
} timing_stats_t;

/* BSRR tek bir yazmayla pini değiştirir: okuma-değiştirme-yazma yok, kesme
 * araya girse de diğer pinler bozulmaz. Üst 16 bit sıfırlar, alt 16 bit kurar. */
static inline void timing_pin_high(void)
{
    TIMING_GPIO_Port->BSRR = TIMING_Pin;
}

static inline void timing_pin_low(void)
{
    TIMING_GPIO_Port->BSRR = (uint32_t)TIMING_Pin << 16;
}

/* t0'dan (dwt_cycles()) bu yana geçen süreyi s'ye ekler. */
void timing_record(volatile timing_stats_t *s, uint32_t t0);

#endif /* TIMING_H */
