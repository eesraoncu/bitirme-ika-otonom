#include "recovery/recovery.h"

bool recovery_arrived(geo_point_t pos, geo_point_t goal)
{
    int64_t dx = (int64_t)pos.x_cm - goal.x_cm;
    int64_t dy = (int64_t)pos.y_cm - goal.y_cm;
    int64_t r = RECOVERY_ARRIVAL_CM;
    return dx * dx + dy * dy <= r * r;
}
