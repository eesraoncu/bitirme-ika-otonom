#include "rules/limits/limits.h"

#include <stdbool.h>

static int32_t clamp(int32_t v, int32_t lo, int32_t hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

int16_t limit_axis(int16_t cmd, int16_t prev, int16_t step, int16_t max)
{
    /* int32: prev ± step ve |cmd| int16 sınırında taşmasın (−32768'in tersi yok) */
    int32_t c = cmd, p = prev;
    int32_t mag_c = c < 0 ? -c : c;
    int32_t mag_p = p < 0 ? -p : p;
    bool accelerating = (c * p >= 0) && mag_c > mag_p;
    if (accelerating) {
        c = clamp(c, p - step, p + step);
    }
    return (int16_t)clamp(c, -max, max);
}

limit_result_t limit_speed_cmd(uint16_t limit_mm_s)
{
    if (limit_mm_s == 0u) {
        return LIMIT_NOT_POSITIVE;
    }
    if (limit_mm_s > LIMIT_V_MAX_MM_S) {
        return LIMIT_ABOVE_MAX;
    }
    return LIMIT_OK;
}
