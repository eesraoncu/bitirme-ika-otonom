/* CAN kanalı: FDCAN1 (bekçi, PA11/PA12) ve FDCAN2 (araç, PB12/PB13),
 * klasik CAN, 500 kbit/s (docs/protocol.md §8).
 *
 * İki düğüm aynı kartta (K-002). Bu modül yalnızca çerçeve taşır, yükün
 * ne anlama geldiğine bakmaz. Hiçbir fonksiyon beklemez: gönderme donanımın
 * 3 yerlik tamponuna, alma donanımın 3 yerlik alma kuyruğuna (Rx FIFO0)
 * dayanır. Kesme yok, app_loop() yoklar. */
#ifndef CAN_LINK_H
#define CAN_LINK_H

#include <stdbool.h>
#include <stdint.h>

/* Klasik CAN'de bir çerçevenin en fazla yükü. */
#define CAN_LINK_DATA_MAX 8u

typedef enum {
    CAN_LINK_GUARD,     /* FDCAN1, bekçi. Gönderme tamponu kuyruk modunda. */
    CAN_LINK_VEHICLE,   /* FDCAN2, araç tarafı. Gönderme tamponu FIFO modunda. */
} can_link_node_t;

typedef struct {
    uint16_t id;                        /* 11 bitlik kimlik */
    uint8_t  len;                       /* 0 … CAN_LINK_DATA_MAX */
    uint8_t  data[CAN_LINK_DATA_MAX];
} can_frame_t;

/* Bir kez, MX_FDCAN1_Init() ve MX_FDCAN2_Init()'ten sonra çağrılır.
 * Filtreleri kurar ve iki birimi başlatır. Birim CubeMX'te iç döngü
 * modundaysa kendi gönderdiği kimlikleri de kabul eder. */
void can_link_init(void);

/* Çerçeveyi gönderme tamponuna koyar ve hemen döner. Tampon doluysa ya da
 * çerçeve uygun değilse false döner ve hiçbir şey göndermez. */
bool can_link_send(can_link_node_t node, const can_frame_t *f);

/* Alma kuyruğundaki en eski çerçeveyi out'a yazar ve true döner. Kuyruk
 * boşsa false döner. */
bool can_link_receive(can_link_node_t node, can_frame_t *out);

#endif /* CAN_LINK_H */
