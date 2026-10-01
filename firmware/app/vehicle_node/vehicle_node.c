#include "vehicle_node/vehicle_node.h"

#include <stdbool.h>
#include <stddef.h>

#include "links/can_link.h"
#include "proto_msgs.h"

volatile vehicle_node_errors_t vehicle_node_errors;

/* CAN kimliği → mesaj. Elle yazılmaz, açılışta üretilmiş mesaj tablosundan
 * çıkarılır (K-003): araç kanalına giden ve CAN kimliği olan her mesaj. */
#define MAP_MAX 8u

static struct {
    uint16_t can_id;
    const proto_msg_info_t *info;
} map[MAP_MAX];
static size_t map_n;

void vehicle_node_init(void)
{
    map_n = 0;
    for (unsigned id = 0; id <= UINT8_MAX && map_n < MAP_MAX; id++) {
        const proto_msg_info_t *info = proto_msg_info((uint8_t)id);
        if (info != NULL && info->has_can_id && info->channel == PROTO_CH_VEHICLE &&
            info->dir == PROTO_DIR_BOARD_TO_PC) {
            map[map_n].can_id = info->can_id;
            map[map_n].info = info;
            map_n++;
        }
    }
}

static const proto_msg_info_t *lookup(uint16_t can_id)
{
    for (size_t i = 0; i < map_n; i++) {
        if (map[i].can_id == can_id) {
            return map[i].info;
        }
    }
    return NULL;
}

void vehicle_node_poll(channel_t *vehicle_ch)
{
    can_frame_t cf;
    while (can_link_receive(CAN_LINK_VEHICLE, &cf)) {
        const proto_msg_info_t *info = lookup(cf.id);
        if (info == NULL || cf.len != info->size) {
            vehicle_node_errors.unknown_can_id++;
            continue;
        }
        (void)channel_send(vehicle_ch, info->id, cf.data, cf.len);
    }
}

void vehicle_node_telemetry(const frame_t *f)
{
    can_frame_t cf = { .id = PROTO_CAN_ID_TELEMETRY, .len = (uint8_t)f->payload_len };
    for (size_t i = 0; i < f->payload_len && i < CAN_LINK_DATA_MAX; i++) {
        cf.data[i] = f->payload[i];
    }
    if (!can_link_send(CAN_LINK_VEHICLE, &cf)) {
        vehicle_node_errors.can_tx_full++;
    }
}
