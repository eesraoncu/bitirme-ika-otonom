#include "app.h"

#include <string.h>

#include "main.h"   /* HAL (HAL_GetTick) ve BSP (BSP_LED_*) */
#include "fdcan.h"  /* Geçici: Faz 2.4 testi birimin durumunu HAL'den soruyor */
#include "auth/hmac_sha256.h"
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

/* ---- Faz 2.6: HMAC süre ölçümü (geçici) ----------------------------------
 *
 * A. Tam HMAC: anahtar her seferinde yeniden hazırlanır (frame.c'nin
 *    compute_tag'i böyle). 4 SHA-256 blok işlemi: ipad, opad, veri, dış özet.
 * B. Hazırlanmış bağlam kopyalanır, yalnızca veri ve dış özet işlenir: 2 blok.
 * C. hmac_tag_equal: etiketler eşit, fark 0. baytta, fark 7. baytta.
 *    Üçünün süresi aynı olmalı.
 * D. Aynı üç durum memcmp ile. Kontrol deneyi: memcmp ilk farkta durur,
 *    süresi farklı çıkmalı. Çıkmazsa ölçüm bu farkı göremiyor demektir.
 *
 * Girdi test_vectors.json'daki VERDICT çerçevesi: en uzun yük (23 bayt),
 * test anahtarı ve test oturumu. Kartta hesaplanan etiket vektördekiyle
 * karşılaştırılır (tag_ok): kriptografi kodu ilk kez ARM'da çalışıyor.
 *
 * Her ölçüm HMAC_RUNS kez tekrarlanır, en kısa ve en uzun süre saklanır.
 * Kesmeler her ölçümün süresince kapalı: SysTick ya da UART kesmesi araya
 * girip süreyi uzatmasın. Bir ölçüm 1 ms'den çok kısa olduğu için SysTick
 * kesmesi kaybolmaz, yalnızca ölçüm bitince işlenir. */

#define HMAC_TEST_MAGIC  0x4AC7E57Du
#define HMAC_RUNS        1000u

typedef struct {
    uint32_t min;
    uint32_t max;
} cycles_t;

/* Karttan salt okuma ile okunur. Süreler çevrim (170 MHz'de 5,9 ns) ve
 * empty dahil, yani her birinden empty.min çıkarılmalı. */
typedef struct {
    uint32_t magic;          /* HMAC_TEST_MAGIC: ölçüm sonuna kadar çalıştı */
    uint32_t tag_ok;         /* 1: A ve B'nin etiketi test vektörüyle aynı */
    cycles_t empty;          /* boş fonksiyon: çağrının ve ölçümün kendi maliyeti */
    cycles_t hmac_full;      /* A */
    cycles_t hmac_prepared;  /* B */
    cycles_t equal_same;     /* C */
    cycles_t equal_diff0;
    cycles_t equal_diff7;
    cycles_t memcmp_same;    /* D */
    cycles_t memcmp_diff0;
    cycles_t memcmp_diff7;
} hmac_test_result_t;

volatile hmac_test_result_t hmac_test_result;

static const uint8_t test_key[32] = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
    0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
};

/* session_id = 0x1234ABCD, küçük uçlu (proto_put_u32 gibi). */
static const uint8_t test_sid[4] = { 0xCD, 0xAB, 0x34, 0x12 };

/* VERDICT: başlık (9) ‖ yük (23). */
static const uint8_t test_body[PROTO_HEADER_BYTES + PROTO_MAX_PAYLOAD_BYTES] = {
    0x90, 0xF3, 0x03, 0x00, 0x00, 0xBE, 0xC3, 0x00, 0x00,
    0xEF, 0xCD, 0xAB, 0x89, 0x01, 0x07, 0x35, 0x5C, 0x79, 0xFE, 0xFF, 0xA5,
    0x86, 0x01, 0x00, 0x5A, 0x79, 0xFE, 0xFF, 0xEF, 0x03, 0x10, 0xFC,
};

static const uint8_t test_tag[PROTO_TAG_BYTES] = {
    0xD1, 0x8F, 0xD5, 0xB0, 0x30, 0xE0, 0x2C, 0x5B,
};

/* Ölçülen fonksiyonların girdisi ve çıktısı. Fonksiyonlar parametresiz,
 * çünkü hepsi aynı measure() ile ölçülüyor. */
static hmac_sha256_ctx_t prepared;
static uint8_t digest[SHA256_DIGEST_BYTES];
static uint8_t tag_same[PROTO_TAG_BYTES];
static uint8_t tag_diff0[PROTO_TAG_BYTES];
static uint8_t tag_diff7[PROTO_TAG_BYTES];
static const uint8_t *tag_other;
/* volatile: sonuç kullanılmasa da derleyici karşılaştırmayı silmesin. */
static volatile bool tag_sink;

static void run_nothing(void)
{
}

static void run_hmac_full(void)
{
    hmac_sha256_ctx_t c;
    hmac_sha256_init(&c, test_key, sizeof test_key);
    hmac_sha256_update(&c, test_sid, sizeof test_sid);
    hmac_sha256_update(&c, test_body, sizeof test_body);
    hmac_sha256_final(&c, digest);
}

static void run_hmac_prepared(void)
{
    hmac_sha256_ctx_t c = prepared;
    hmac_sha256_update(&c, test_sid, sizeof test_sid);
    hmac_sha256_update(&c, test_body, sizeof test_body);
    hmac_sha256_final(&c, digest);
}

static void run_tag_equal(void)
{
    tag_sink = hmac_tag_equal(test_tag, tag_other, PROTO_TAG_BYTES);
}

static void run_memcmp(void)
{
    tag_sink = (memcmp(test_tag, tag_other, PROTO_TAG_BYTES) == 0);
}

static void measure(void (*fn)(void), volatile cycles_t *out)
{
    uint32_t lo = UINT32_MAX;
    uint32_t hi = 0u;
    for (uint32_t i = 0; i < HMAC_RUNS; i++) {
        __disable_irq();
        uint32_t t0 = dwt_cycles();
        fn();
        uint32_t dt = dwt_cycles() - t0;
        __enable_irq();
        if (dt < lo) {
            lo = dt;
        }
        if (dt > hi) {
            hi = dt;
        }
    }
    out->min = lo;
    out->max = hi;
}

static void measure_compare(void (*fn)(void), volatile cycles_t *same,
                            volatile cycles_t *diff0, volatile cycles_t *diff7)
{
    tag_other = tag_same;
    measure(fn, same);
    tag_other = tag_diff0;
    measure(fn, diff0);
    tag_other = tag_diff7;
    measure(fn, diff7);
}

static void run_hmac_test(void)
{
    hmac_sha256_init(&prepared, test_key, sizeof test_key);

    memcpy(tag_same, test_tag, sizeof tag_same);
    memcpy(tag_diff0, test_tag, sizeof tag_diff0);
    memcpy(tag_diff7, test_tag, sizeof tag_diff7);
    tag_diff0[0] ^= 0x01u;
    tag_diff7[PROTO_TAG_BYTES - 1u] ^= 0x01u;

    measure(run_nothing, &hmac_test_result.empty);

    measure(run_hmac_full, &hmac_test_result.hmac_full);
    bool ok = memcmp(digest, test_tag, PROTO_TAG_BYTES) == 0;
    memset(digest, 0, sizeof digest);   /* B kendi sonucunu yazmalı */
    measure(run_hmac_prepared, &hmac_test_result.hmac_prepared);
    ok = ok && memcmp(digest, test_tag, PROTO_TAG_BYTES) == 0;
    hmac_test_result.tag_ok = ok;

    measure_compare(run_tag_equal, &hmac_test_result.equal_same,
                    &hmac_test_result.equal_diff0, &hmac_test_result.equal_diff7);
    measure_compare(run_memcmp, &hmac_test_result.memcmp_same,
                    &hmac_test_result.memcmp_diff0, &hmac_test_result.memcmp_diff7);

    hmac_test_result.magic = HMAC_TEST_MAGIC;
}

/* ---- Uygulama ------------------------------------------------------------ */

/* Faz 2.2 ve 2.5 yankı testi: port'tan gelen her baytı aynı porta geri
 * gönder. Gönderme meşgulken okunmaz, baytlar dairesel tamponda bekler.
 * Faz 2.6'da baytlar burada çerçeveleyiciye verilecek. */
static void echo(serial_link_port_t port)
{
    if (serial_link_tx_ready(port)) {
        uint8_t buf[SERIAL_LINK_TX_MAX];
        size_t n = serial_link_read(port, buf, sizeof buf);
        if (n > 0u) {
            (void)serial_link_send(port, buf, n);
        }
    }
}

void app_init(void)
{
    dwt_init();
    serial_link_init();
    can_link_init();
    run_can_test();
    run_hmac_test();
}

void app_loop(void)
{
    echo(SERIAL_LINK_AGENT);
    echo(SERIAL_LINK_VEHICLE);

    uint32_t period = can_test_result.passed ? PULSE_PERIOD_MS : FAIL_PERIOD_MS;
    uint32_t on     = can_test_result.passed ? PULSE_ON_MS     : FAIL_ON_MS;
    if (HAL_GetTick() % period < on) {
        BSP_LED_On(LED_GREEN);
    } else {
        BSP_LED_Off(LED_GREEN);
    }
}
