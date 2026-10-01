#include "app.h"

#include <string.h>

#include "main.h"   /* HAL (HAL_GetTick) ve BSP (BSP_LED_*) */
#include "fdcan.h"  /* Geçici: Faz 2.4 testi birimin durumunu HAL'den soruyor */
#include "rng.h"    /* CubeMX: hrng, oturum kimliği için */
#include "channel/channel.h"
#include "links/can_link.h"
#include "links/serial_link.h"
#include "proto_msgs.h"
#include "timing/dwt.h"

/* Faz 2.1 doğrulaması: kısa bir "nabız". Saniyede bir, 100 ms yanık.
 * LED testinin 500/500 deseninden gözle ayırt edilsin diye farklı seçildi.
 * LED bu desenle yanıp sönüyorsa HSE kristali başlamış ve PLL 170 MHz'e
 * kilitlenmiş demektir. Aksi hâlde SystemClock_Config() hata verir ve
 * program Error_Handler()'da takılırdı. Nabız sürdükçe app_loop()'un
 * takılmadığı da görülür. */
#define PULSE_PERIOD_MS 1000u
#define PULSE_ON_MS      100u

/* Faz 2.4 kaldıysa: saniyede 5 yanıp sönme. Nabızdan tek bakışta ayrılır. */
#define FAIL_PERIOD_MS   200u
#define FAIL_ON_MS       100u

/* ---- Faz 2.4: FDCAN gerçek hat testi (geçici) ----------------------------
 *
 * FDCAN1 → SN65HVD230 → CANH/CANL → SN65HVD230 → FDCAN2. Birimler Normal
 * modda, her biri yalnızca karşı düğümün kimliklerini alır (can_link,
 * filtre 0).
 *
 * A. FDCAN1 (kuyruk modu) DRIVE verir, hatta çıkmasını bekler, sonra GOAL
 *    ve HALT verir. FDCAN2 alır. Beklenen sıra DRIVE, HALT, GOAL.
 * C. FDCAN2 TELEMETRY verir, FDCAN1 alır.
 *
 * Faz 2.3'teki B (FIFO modu kontrol deneyi) burada yok: FDCAN1'in filtresi
 * araçtan komut kimliği almaz. Deney iç döngüde yapıldı (K-019).
 *
 * Her gelen çerçevenin uzunluğu ve baytları gönderilenle karşılaştırılır.
 * Test app_init()'te bir kez çalışır ve beklemeli yazıldı. Toplam 2 ms
 * sürmez, her bekleme süre sınırıyla korunur. */

#define TEST_MAGIC       0xCA7E57EDu
#define TEST_TIMEOUT_MS  10u
#define ORDER_N          3u

/* İlk kalan adım. 0 = hiçbiri. Onlar basamağı testi (A = 1x, C = 3x),
 * birler basamağı adımı söyler. */
#define STEP_IDLE     1u   /* birimlerden biri senkronize olup boşa çıkmadı */
#define STEP_SEND     2u   /* gönderme tamponu çerçeveyi kabul etmedi */
#define STEP_ON_WIRE  3u   /* DRIVE hatta çıkmadı */
#define STEP_RECEIVE  4u   /* beklenen sayıda çerçeve gelmedi (ör. ACK yok) */

/* Karttan salt okuma ile okunur (docs/STATUS.md). Her alan 32 bit, çıktının
 * her sözcüğü bir alan olsun diye. volatile: kodda hiç okunmadığı için
 * derleyici yazmaları silmesin. */
typedef struct {
    uint32_t magic;                  /* TEST_MAGIC: test sonuna kadar çalıştı */
    uint32_t passed;                 /* 1: hepsi geçti */
    uint32_t fail_step;
    uint32_t queue_n;                /* A'da gelen çerçeve sayısı */
    uint32_t queue_order[ORDER_N];   /* A'da gelen kimlikler, geliş sırasıyla */
    uint32_t payload_errors;         /* uzunluğu ya da baytı tutmayan çerçeve */
    uint32_t telemetry_ok;
    uint32_t tec1, rec1, tec2, rec2; /* FDCAN'in kendi hata sayaçları */
} can_test_result_t;

volatile can_test_result_t can_test_result;

static void fail(uint32_t step)
{
    if (can_test_result.fail_step == 0u) {   /* ilk hatayı sakla */
        can_test_result.fail_step = step;
    }
}

static bool wait_activity(FDCAN_HandleTypeDef *h, uint32_t state)
{
    uint32_t t0 = HAL_GetTick();
    do {
        FDCAN_ProtocolStatusTypeDef ps;
        (void)HAL_FDCAN_GetProtocolStatus(h, &ps);
        if (ps.Activity == state) {
            return true;
        }
    } while (HAL_GetTick() - t0 < TEST_TIMEOUT_MS);
    return false;
}

static bool wait_receive(can_link_node_t node, can_frame_t *out)
{
    uint32_t t0 = HAL_GetTick();
    do {
        if (can_link_receive(node, out)) {
            return true;
        }
    } while (HAL_GetTick() - t0 < TEST_TIMEOUT_MS);
    return false;
}

/* Gelen çerçeveyi aynı kimlikle gönderilenle karşılaştırır. */
static void check_payload(const can_frame_t *got, const can_frame_t *sent,
                          size_t n_sent)
{
    for (size_t i = 0; i < n_sent; i++) {
        if (sent[i].id == got->id) {
            if (sent[i].len != got->len ||
                memcmp(sent[i].data, got->data, got->len) != 0) {
                can_test_result.payload_errors++;
            }
            return;
        }
    }
    can_test_result.payload_errors++;   /* gönderilmemiş bir kimlik */
}

/* A. tx gönderir, rx alır. Gelen kimlikleri order'a yazar, kaç çerçeve
 * geldiğini döndürür. */
static uint32_t run_order_test(can_link_node_t tx, FDCAN_HandleTypeDef *tx_h,
                               can_link_node_t rx, FDCAN_HandleTypeDef *rx_h,
                               volatile uint32_t *order, uint32_t step_base)
{
    proto_drive_t drive = { .v_mm_s = 250, .w_mrad_s = -800 };
    proto_goal_t  goal  = { .x_cm = 150, .y_cm = -320, .yaw_mrad = 1571,
                            .source = PROTO_GOAL_SOURCE_AGENT };
    proto_halt_t  halt  = { .duration_s = 7 };

    /* Veriliş sırası: DRIVE, GOAL, HALT. */
    can_frame_t sent[ORDER_N] = {
        { .id = PROTO_CAN_ID_DRIVE, .len = PROTO_SIZE_DRIVE },
        { .id = PROTO_CAN_ID_GOAL,  .len = PROTO_SIZE_GOAL  },
        { .id = PROTO_CAN_ID_HALT,  .len = PROTO_SIZE_HALT  },
    };
    proto_drive_encode(&drive, sent[0].data);
    proto_goal_encode(&goal, sent[1].data);
    proto_halt_encode(&halt, sent[2].data);

    /* Başlatılan birim hatta 11 bitlik sessizlik görene kadar gönderemez.
     * O sırada üç mesaj da tamponda birikir ve HALT, DRIVE'ın da önüne
     * geçerdi. Test her açılışta aynı sonucu versin diye önce beklenir.
     * Alıcı da beklenir: çerçeveyi ACK biti verilmeden başarılı sayılmaz.
     * Senkronize olmamış alıcı ACK vermez, gönderen TEC'i 8 artırıp yeniden
     * dener. */
    if (!wait_activity(tx_h, FDCAN_COM_STATE_IDLE) ||
        !wait_activity(rx_h, FDCAN_COM_STATE_IDLE)) {
        fail(step_base + STEP_IDLE);
        return 0;
    }
    if (!can_link_send(tx, &sent[0])) {
        fail(step_base + STEP_SEND);
        return 0;
    }
    /* DRIVE hatta. Başlamış bir gönderim kesilmez, GOAL ile HALT tamponda
     * bekler. Seçim ikisi arasında yapılır. */
    if (!wait_activity(tx_h, FDCAN_COM_STATE_TX)) {
        fail(step_base + STEP_ON_WIRE);
        return 0;
    }
    if (!can_link_send(tx, &sent[1]) || !can_link_send(tx, &sent[2])) {
        fail(step_base + STEP_SEND);
        return 0;
    }

    uint32_t n = 0;
    can_frame_t got;
    while (n < ORDER_N && wait_receive(rx, &got)) {
        order[n++] = got.id;
        check_payload(&got, sent, ORDER_N);
    }
    if (n != ORDER_N) {
        fail(step_base + STEP_RECEIVE);
    }
    return n;
}

static void run_telemetry_test(void)
{
    proto_telemetry_t tel = { .x_cm = -45, .y_cm = 812, .yaw_mrad = -3000 };
    can_frame_t sent = { .id = PROTO_CAN_ID_TELEMETRY,
                         .len = PROTO_SIZE_TELEMETRY };
    proto_telemetry_encode(&tel, sent.data);

    if (!can_link_send(CAN_LINK_VEHICLE, &sent)) {
        fail(30u + STEP_SEND);
        return;
    }
    can_frame_t got;
    if (!wait_receive(CAN_LINK_GUARD, &got)) {
        fail(30u + STEP_RECEIVE);
        return;
    }
    uint32_t errors_before = can_test_result.payload_errors;
    check_payload(&got, &sent, 1u);
    can_test_result.telemetry_ok = (can_test_result.payload_errors == errors_before);
}

static void run_can_test(void)
{
    static const uint32_t queue_expected[ORDER_N] =
        { PROTO_CAN_ID_DRIVE, PROTO_CAN_ID_HALT, PROTO_CAN_ID_GOAL };

    can_test_result.queue_n = run_order_test(CAN_LINK_GUARD, &hfdcan1,
                                             CAN_LINK_VEHICLE, &hfdcan2,
                                             can_test_result.queue_order, 10u);
    run_telemetry_test();

    FDCAN_ErrorCountersTypeDef ec;
    (void)HAL_FDCAN_GetErrorCounters(&hfdcan1, &ec);
    can_test_result.tec1 = ec.TxErrorCnt;
    can_test_result.rec1 = ec.RxErrorCnt;
    (void)HAL_FDCAN_GetErrorCounters(&hfdcan2, &ec);
    can_test_result.tec2 = ec.TxErrorCnt;
    can_test_result.rec2 = ec.RxErrorCnt;

    bool ok = can_test_result.fail_step == 0u &&
              can_test_result.payload_errors == 0u &&
              can_test_result.telemetry_ok == 1u &&
              can_test_result.tec1 == 0u && can_test_result.rec1 == 0u &&
              can_test_result.tec2 == 0u && can_test_result.rec2 == 0u;
    for (size_t i = 0; i < ORDER_N; i++) {
        ok = ok && can_test_result.queue_order[i] == queue_expected[i];
    }
    can_test_result.passed = ok;
    can_test_result.magic = TEST_MAGIC;
}

/* ---- Uygulama ------------------------------------------------------------ */

static channel_t agent_ch;
static channel_t vehicle_ch;

/* Kartın durumu. Durum makinesi Faz 2.6 c'de gelecek. O zamana kadar kart
 * açıldığı gibi HOLD'da kalır (docs/RULES.md §5.2). Telemetri henüz
 * işlenmiyor, yaşı doymuş değerde. */
static channel_board_t board = {
    .state = PROTO_BOARD_STATE_HOLD,
    .reject_streak = 0u,
    .telemetry_age_ms = UINT16_MAX,
};

/* Oturum kimliği, açılışta donanım RNG'den (docs/protocol.md §5.2). RNG
 * hata verirse (saat ya da tohum hatası) kart çalışmaz: tahmin edilebilir ya
 * da önceki açılışla aynı bir kimlik, eski oturumun çerçevelerini yeniden
 * geçerli kılabilirdi. */
static uint32_t new_session_id(void)
{
    uint32_t id;
    if (HAL_RNG_GenerateRandomNumber(&hrng, &id) != HAL_OK) {
        Error_Handler();
    }
    return id;
}

static void on_agent_frame(channel_t *ch, const frame_t *f)
{
    if (f->type == PROTO_ID_HEARTBEAT) {
        /* Uzunluk frame_decode'da denetlendi. Yine de sonuca bakılır:
         * çözülmemiş bir yük hiçbir zaman kullanılmasın. */
        proto_heartbeat_t hb;
        if (!proto_heartbeat_decode(f->payload, f->payload_len, &hb)) {
            return;
        }
        proto_heartbeat_ack_t ack = {
            .echo_pc_ms = hb.echo_pc_ms,
            .state = board.state,
            .reject_streak = board.reject_streak,
        };
        uint8_t p[PROTO_SIZE_HEARTBEAT_ACK];
        proto_heartbeat_ack_encode(&ack, p);
        (void)channel_send(ch, PROTO_ID_HEARTBEAT_ACK, p, sizeof p);
    }
    /* Zaman aşımı Faz 2.6 d'de, görev ve hız komutları c'de. */
}

static void on_vehicle_frame(channel_t *ch, const frame_t *f)
{
    /* TELEMETRY Faz 2.6 c'de işlenecek. */
    (void)ch;
    (void)f;
}

void app_init(void)
{
    dwt_init();
    serial_link_init();
    can_link_init();
    run_can_test();

    uint32_t session_id = new_session_id();
    channel_init(&agent_ch, SERIAL_LINK_AGENT, PROTO_CH_AGENT, session_id);
    channel_init(&vehicle_ch, SERIAL_LINK_VEHICLE, PROTO_CH_VEHICLE, session_id);
}

void app_loop(void)
{
    uint32_t now = HAL_GetTick();
    channel_poll(&agent_ch, now, &board, on_agent_frame);
    channel_poll(&vehicle_ch, now, &board, on_vehicle_frame);
    channel_service(&agent_ch, now, &board);
    channel_service(&vehicle_ch, now, &board);

    uint32_t period = can_test_result.passed ? PULSE_PERIOD_MS : FAIL_PERIOD_MS;
    uint32_t on     = can_test_result.passed ? PULSE_ON_MS     : FAIL_ON_MS;
    if (now % period < on) {
        BSP_LED_On(LED_GREEN);
    } else {
        BSP_LED_Off(LED_GREEN);
    }
}
