/* Kalp atışı (docs/RULES.md §3.5).
 *
 * Köprü 100 ms'de bir HEARTBEAT gönderir. 500 ms gelmezse bağlantı ölü
 * sayılır. Süreyi yazılım döngüsü değil, donanım zamanlayıcısı TIM6 ölçer
 * (CubeMX: 10 kHz, 5 000 sayımda taşar = 500 ms). Her geçerli HEARTBEAT
 * sayacı sıfırlar; sayaç taşarsa kesme gelir. Ana döngü takılsa bile zaman
 * aşımı kesmeyle yakalanır.
 *
 * Açılışta bağlantı ölüdür: köprü henüz hiç kalp atışı göndermedi. */
#ifndef HEARTBEAT_H
#define HEARTBEAT_H

#include <stdbool.h>

/* Bir kez, MX_TIM6_Init()'ten sonra. Zamanlayıcıyı kesmeyle başlatır. */
void heartbeat_init(void);

/* İmzası ve sayacı doğrulanmış her HEARTBEAT'te çağrılır. */
void heartbeat_feed(void);

/* Son HEARTBEAT'ten beri 500 ms geçmediyse true. */
bool heartbeat_alive(void);

/* Bağlantı canlıyken öldüyse bir kez true döner, sonra false. Durum
 * makinesi bununla HOLD'a geçer. */
bool heartbeat_take_lost(void);

#endif /* HEARTBEAT_H */
