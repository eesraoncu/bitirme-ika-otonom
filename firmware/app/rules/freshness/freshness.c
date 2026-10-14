#include "rules/freshness/freshness.h"

int32_t time_age_ms(uint32_t now_ms, uint32_t ts_ms)
{
    /* İşaretsiz fark, sonra işaretli yorum: 2³¹'den büyük fark "ileride" demek.
     * (int32_t) dönüşümü yerine açık hesap: C'de taşan dönüşüm tanımsız değil
     * ama gerçekleştirmeye bağlı. */
    uint32_t diff = now_ms - ts_ms;
    return diff <= (uint32_t)INT32_MAX ? (int32_t)diff : -(int32_t)(0u - diff - 1u) - 1;
}

freshness_result_t freshness_check(uint32_t now_ms, uint32_t ts_ms, int32_t *age_ms)
{
    int32_t age = time_age_ms(now_ms, ts_ms);
    *age_ms = age;
    if (age > FRESHNESS_MAX_AGE_MS) {
        return FRESHNESS_TOO_OLD;
    }
    if (age < -FRESHNESS_MAX_FUTURE_MS) {
        return FRESHNESS_FROM_FUTURE;
    }
    return FRESHNESS_OK;
}
