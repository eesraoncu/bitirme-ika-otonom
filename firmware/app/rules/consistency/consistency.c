#include "rules/consistency/consistency.h"

#include "rules/freshness/freshness.h"
#include "rules/limits/limits.h"

/* ⌊√n⌋, n < 2⁶⁴ için bit bit (64 adım, süresi sabit). */
static uint32_t isqrt64(uint64_t n)
{
    uint64_t root = 0, bit = 1ull << 62;
    while (bit > n) {
        bit >>= 2;
    }
    while (bit != 0u) {
        if (n >= root + bit) {
            n -= root + bit;
            root = (root >> 1) + bit;
        } else {
            root >>= 1;
        }
        bit >>= 2;
    }
    return (uint32_t)root;
}

consistency_result_t consistency_check(uint32_t now_ms, geo_point_t belief, uint32_t belief_ts_ms,
                                       geo_point_t telemetry, uint32_t telemetry_age_ms,
                                       consistency_detail_t *d)
{
    d->value = 0;
    d->lo = 0;
    d->hi = 0;
    if (telemetry_age_ms > CONSISTENCY_TELEMETRY_MAX_AGE_MS) {
        d->value = telemetry_age_ms > (uint32_t)INT32_MAX ? INT32_MAX : (int32_t)telemetry_age_ms;
        d->hi = CONSISTENCY_TELEMETRY_MAX_AGE_MS;
        return CONSISTENCY_NO_TELEMETRY;
    }
    int32_t dt = time_age_ms(now_ms, belief_ts_ms);
    if (dt < -FRESHNESS_MAX_FUTURE_MS) {
        d->value = dt;
        d->lo = -FRESHNESS_MAX_FUTURE_MS;
        return CONSISTENCY_BELIEF_FROM_FUTURE;
    }
    if (dt > CONSISTENCY_MAX_BELIEF_AGE_MS) {
        d->value = dt;
        d->hi = CONSISTENCY_MAX_BELIEF_AGE_MS;
        return CONSISTENCY_BELIEF_TOO_OLD;
    }
    /* tol (cm) = d₀ + v_max (mm/s) × Δt (ms) / 10 000; −50…0 ms aralığında Δt = 0 sayılır */
    int64_t tol = CONSISTENCY_D0_CM + (int64_t)LIMIT_V_MAX_MM_S * (dt > 0 ? dt : 0) / 10000;
    int64_t dx = (int64_t)belief.x_cm - telemetry.x_cm;
    int64_t dy = (int64_t)belief.y_cm - telemetry.y_cm;
    uint64_t dist2 = (uint64_t)(dx * dx + dy * dy);
    if (dist2 <= (uint64_t)(tol * tol)) {
        return CONSISTENCY_OK;
    }
    d->value = (int32_t)isqrt64(dist2);
    d->hi = (int32_t)tol;
    return CONSISTENCY_TOO_FAR;
}
