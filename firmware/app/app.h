/* Bekçi kartının uygulama katmanı.
 *
 * CubeMX'in ürettiği main.c yalnızca bu iki fonksiyonu çağırır (CLAUDE.md:
 * CubeMX dosyalarına kod yazılmaz). Uygulamanın geri kalanı app/ altındaki
 * klasörlerde yaşar. */
#ifndef APP_H
#define APP_H

/* Bir kez, tüm CubeMX ve BSP başlatmalarından sonra çağrılır. */
void app_init(void);

/* Sonsuz döngünün her turunda çağrılır. Asla beklememeli. */
void app_loop(void);

#endif /* APP_H */
