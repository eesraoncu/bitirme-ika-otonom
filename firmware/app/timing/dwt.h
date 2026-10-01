/* DWT çevrim sayacı: kodun kaç saat çevriminde çalıştığını ölçer (K-009).
 *
 * DWT (Data Watchpoint and Trace), Cortex-M4 çekirdeğinin içindeki hata
 * ayıklama birimidir. İçindeki CYCCNT yazmacı her çekirdek saat çevriminde
 * 1 artar: 170 MHz'de bir çevrim 5,9 ns. 32 bit olduğu için 2^32 çevrimde
 * (~25 s) başa döner. İki okuma arasındaki fark işaretsiz çıkarmayla
 * alınırsa bir kez başa dönmüş olması sonucu bozmaz.
 *
 * Hata ayıklayıcı bağlı olmasa da çalışır, ama önce açılması gerekir. */
#ifndef DWT_H
#define DWT_H

#include <stdint.h>

#include "stm32g4xx.h"   /* CMSIS: DWT ve CoreDebug yazmaçları */

/* Sayacı açar ve sıfırlar. Bir kez, ölçümden önce çağrılır. */
void dwt_init(void);

/* Sayacın anlık değeri. inline: ölçülen koda çağrı maliyeti eklenmesin. */
static inline uint32_t dwt_cycles(void)
{
    return DWT->CYCCNT;
}

#endif /* DWT_H */
