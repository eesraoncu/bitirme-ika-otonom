#include "links/can_link.h"

#include <string.h>

#include "fdcan.h"        /* hfdcan1, hfdcan2 (CubeMX), HAL, Error_Handler() */
#include "proto_msgs.h"   /* PROTO_CAN_ID_* (messages.yaml'dan üretilir, K-003) */

/* HAL_FDCAN_GetRxMessage() çerçevenin uzunluk alanına bakıp 64 bayta kadar
 * kopyalar (CAN FD'nin en uzun yükü). Klasik CAN'de 8'i aşan uzunluk bozuk
 * çerçeve demektir ama kopyalama buna bakmadan yapılır. 8 baytlık diziye
 * doğrudan alınsaydı bozuk bir çerçeve belleği ezerdi. */
#define RX_RAW_MAX 64u

/* 11 bitlik kimliğin en büyük değeri. */
#define STD_ID_MAX 0x7FFu

/* Filtreye uyduğu hâlde uzunluğu 8'i aştığı için atılan çerçeve sayısı.
 * Şimdilik yalnızca hata ayıklayıcıdan okunur. */
static uint32_t rx_dropped;

static FDCAN_HandleTypeDef *handle(can_link_node_t node)
{
    return node == CAN_LINK_GUARD ? &hfdcan1 : &hfdcan2;
}

/* first … last aralığındaki kimlikleri alma kuyruğuna (Rx FIFO0) alır. */
static void add_range_filter(FDCAN_HandleTypeDef *h, uint32_t index,
                             uint16_t first, uint16_t last)
{
    FDCAN_FilterTypeDef f = {
        .IdType       = FDCAN_STANDARD_ID,
        .FilterIndex  = index,
        .FilterType   = FDCAN_FILTER_RANGE,
        .FilterConfig = FDCAN_FILTER_TO_RXFIFO0,
        .FilterID1    = first,
        .FilterID2    = last,
    };
    if (HAL_FDCAN_ConfigFilter(h, &f) != HAL_OK) {
        Error_Handler();
    }
}

/* Filtre 0: birimin asıl görevi, karşı düğümden gelenler.
 * Filtre 1: yalnızca iç döngüde, birimin kendi gönderdikleri. Mod CubeMX'ten
 * okunur. Faz 2.4'te CubeMX'te Normal seçilince bu filtre kendiliğinden
 * kurulmaz. CubeMX'te birim başına 2 filtre yeri ayrıldı (Std Filters Nbr). */
static void start(FDCAN_HandleTypeDef *h,
                  uint16_t peer_first, uint16_t peer_last,
                  uint16_t own_first, uint16_t own_last)
{
    add_range_filter(h, 0u, peer_first, peer_last);
    if (h->Init.Mode == FDCAN_MODE_INTERNAL_LOOPBACK) {
        add_range_filter(h, 1u, own_first, own_last);
    }

    /* Hiçbir filtreye uymayan 11 ve 29 bitlik kimlikler ile veri taşımayan
     * remote çerçeveler donanımda atılır, işlemciye ulaşmaz. */
    if (HAL_FDCAN_ConfigGlobalFilter(h, FDCAN_REJECT, FDCAN_REJECT,
                                     FDCAN_REJECT_REMOTE,
                                     FDCAN_REJECT_REMOTE) != HAL_OK) {
        Error_Handler();
    }
    if (HAL_FDCAN_Start(h) != HAL_OK) {
        Error_Handler();
    }
}

void can_link_init(void)
{
    /* Bekçiden araca giden kimlikler HALT … SPEED_LIMIT_SET aralığında.
     * Kimlikler öncelik sırasında verildiği için (docs/protocol.md §8) tek
     * bir aralık filtresi yetiyor. Aradaki tanımsız kimlikler de geçer,
     * onları araç tarafının çözücüsü reddeder. */
    start(&hfdcan1, PROTO_CAN_ID_TELEMETRY, PROTO_CAN_ID_TELEMETRY,
          PROTO_CAN_ID_HALT, PROTO_CAN_ID_SPEED_LIMIT_SET);
    start(&hfdcan2, PROTO_CAN_ID_HALT, PROTO_CAN_ID_SPEED_LIMIT_SET,
          PROTO_CAN_ID_TELEMETRY, PROTO_CAN_ID_TELEMETRY);
}

bool can_link_send(can_link_node_t node, const can_frame_t *f)
{
    if (f->id > STD_ID_MAX || f->len > CAN_LINK_DATA_MAX) {
        return false;
    }
    FDCAN_HandleTypeDef *h = handle(node);

    /* Tampon doluyken de HAL hata döndürürdü, ama handle'daki ErrorCode'a
     * kalıcı bir "FIFO dolu" işareti de yazardı. Önce sormak daha temiz.
     * HAL_FDCAN_GetTxFifoFreeLevel() kullanılamaz: kuyruk modunda tampon
     * boşken de 0 döner. "Dolu" biti (TFQF) iki modda da geçerli. */
    if ((h->Instance->TXFQS & FDCAN_TXFQS_TFQF) != 0u) {
        return false;
    }

    FDCAN_TxHeaderTypeDef hdr = {
        .Identifier          = f->id,
        .IdType              = FDCAN_STANDARD_ID,
        .TxFrameType         = FDCAN_DATA_FRAME,
        .DataLength          = f->len,   /* G4'te FDCAN_DLC_BYTES_n = n (0 … 8) */
        .ErrorStateIndicator = FDCAN_ESI_ACTIVE,
        .BitRateSwitch       = FDCAN_BRS_OFF,
        .FDFormat            = FDCAN_CLASSIC_CAN,
        .TxEventFifoControl  = FDCAN_NO_TX_EVENTS,
        .MessageMarker       = 0u,
    };
    return HAL_FDCAN_AddMessageToTxFifoQ(h, &hdr, f->data) == HAL_OK;
}

bool can_link_receive(can_link_node_t node, can_frame_t *out)
{
    FDCAN_HandleTypeDef *h = handle(node);

    /* Kuyruk en fazla 3 yerlik, döngü en fazla 3 tur döner. */
    while (HAL_FDCAN_GetRxFifoFillLevel(h, FDCAN_RX_FIFO0) > 0u) {
        FDCAN_RxHeaderTypeDef hdr;
        uint8_t raw[RX_RAW_MAX];
        if (HAL_FDCAN_GetRxMessage(h, FDCAN_RX_FIFO0, &hdr, raw) != HAL_OK) {
            return false;
        }
        /* 29 bitlik kimlikler ve remote çerçeveler filtrede atıldı. */
        if (hdr.DataLength > CAN_LINK_DATA_MAX) {
            rx_dropped++;
            continue;
        }
        out->id  = (uint16_t)hdr.Identifier;
        out->len = (uint8_t)hdr.DataLength;
        memcpy(out->data, raw, out->len);
        return true;
    }
    return false;
}
