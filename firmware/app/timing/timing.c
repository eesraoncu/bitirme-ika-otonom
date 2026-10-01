#include "timing/timing.h"

void timing_record(volatile timing_stats_t *s, uint32_t t0)
{
    uint32_t dt = dwt_cycles() - t0;
    if (s->count == 0u || dt < s->min) {
        s->min = dt;
    }
    if (dt > s->max) {
        s->max = dt;
    }
    s->last = dt;
    s->count++;
}
