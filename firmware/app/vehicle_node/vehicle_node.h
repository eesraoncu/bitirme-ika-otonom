/* Araç tarafı düğümü: FDCAN2 (K-002, docs/protocol.md §8).
 *
 * Gerçek bir araçta bekçi kartı ile motor sürücü kartı ayrıdır ve CAN ile
 * konuşur. Burada ikinci kart yok: aynı kartın FDCAN2'si onun yerine geçer.
 * CAN'den gelen onaylı komutu (GOAL, DRIVE, HALT, SPEED_LIMIT_SET) seri
 * çerçeveye sarıp araç kanalından gönderir. Araç kanalından gelen TELEMETRY'yi
 * CAN'e koyar. Karar vermez: yükü olduğu gibi taşır. */
#ifndef VEHICLE_NODE_H
#define VEHICLE_NODE_H

#include <stdint.h>

#include "channel/channel.h"

/* Bir kez, can_link_init()'ten sonra. */
void vehicle_node_init(void);

/* FDCAN2'nin alma kuyruğunu boşaltır, her mesajı araç kanalına koyar. */
void vehicle_node_poll(channel_t *vehicle_ch);

/* Araç kanalından kabul edilmiş bir TELEMETRY'yi FDCAN2'den gönderir. */
void vehicle_node_telemetry(const frame_t *f);

/* Taşınamayan mesajlar. STATUS'ta yok, RAM'den okunur. */
typedef struct {
    uint32_t unknown_can_id;   /* kimliği tabloda olmayan ya da boyu tutmayan */
    uint32_t can_tx_full;      /* FDCAN2'nin gönderme tamponu doluydu */
} vehicle_node_errors_t;

extern volatile vehicle_node_errors_t vehicle_node_errors;

#endif /* VEHICLE_NODE_H */
