#include "guard/guard.h"

#include <string.h>

#include "recovery/recovery.h"

void guard_init(guard_t *g)
{
    memset(g, 0, sizeof *g);
    g->state = PROTO_BOARD_STATE_HOLD;
}

static void verdict(guard_decision_t *out, uint32_t seq, uint8_t result,
                    uint8_t rule, uint8_t reason)
{
    memset(out, 0, sizeof *out);
    out->verdict.ref_seq = seq;
    out->verdict.result = result;
    out->verdict.rule = rule;
    out->verdict.reason = reason;
}

/* MODE retleri sayılmaz: ajanın hatası değil, kartın durumu (§5.4). */
static bool mode_rejects(const guard_t *g, uint32_t seq, guard_decision_t *out)
{
    if (g->state == PROTO_BOARD_STATE_NORMAL) {
        return false;
    }
    verdict(out, seq, PROTO_RESULT_REJECTED, PROTO_RULE_MODE,
            g->state == PROTO_BOARD_STATE_HOLD ? PROTO_REASON_IN_HOLD
                                               : PROTO_REASON_IN_RECOVERY);
    return true;
}

static void content_rejected(guard_t *g)
{
    if (g->reject_streak < UINT8_MAX) {
        g->reject_streak++;
    }
}

/* NORMAL → RECOVERY: hedef hatırlanır ve araca gidecek GOAL'e yazılır. Varış
 * yönü 0: güvenli noktalarda araç her yönde dönebilir (shared/site/tests/
 * test_safe_points.py), yön önemsiz. */
static void enter_recovery(guard_t *g, geo_point_t target, uint8_t source, proto_goal_t *goal)
{
    g->state = PROTO_BOARD_STATE_RECOVERY;
    g->recovery_goal = target;
    g->recovery_timed = false;
    goal->x_cm = target.x_cm;
    goal->y_cm = target.y_cm;
    goal->yaw_mrad = 0;
    goal->source = source;
}

void guard_goto(guard_t *g, const site_t *s, uint32_t seq, bool heartbeat_alive,
                const proto_goto_cmd_t *cmd, guard_decision_t *out)
{
    if (mode_rejects(g, seq, out)) {
        return;
    }

    geo_point_t goal = { cmd->goal_x_cm, cmd->goal_y_cm };
    geofence_result_t r = geofence_check(&s->fence, goal);
    if (r != GEOFENCE_OK) {
        verdict(out, seq, PROTO_RESULT_REJECTED, PROTO_RULE_GEOFENCE,
                r == GEOFENCE_IN_FORBIDDEN ? PROTO_REASON_GOAL_IN_FORBIDDEN
                                           : PROTO_REASON_GOAL_OUTSIDE_ALLOWED);
        geo_point_t hint = site_nearest_safe(s, goal);
        out->verdict.hint_x_cm = hint.x_cm;
        out->verdict.hint_y_cm = hint.y_cm;
        content_rejected(g);
        if (g->reject_streak >= RECOVERY_REJECT_LIMIT && heartbeat_alive) {
            enter_recovery(g, s->home, PROTO_GOAL_SOURCE_RECOVERY_HOME, &out->goal);
            out->send_goal = true;
        }
        return;
    }

    verdict(out, seq, PROTO_RESULT_ACCEPTED, PROTO_RULE_NONE, PROTO_REASON_NONE);
    out->send_goal = true;
    out->goal.x_cm = cmd->goal_x_cm;
    out->goal.y_cm = cmd->goal_y_cm;
    out->goal.yaw_mrad = cmd->goal_yaw_mrad;
    out->goal.source = PROTO_GOAL_SOURCE_AGENT;
    g->reject_streak = 0u;
}

void guard_reset(guard_t *g, uint32_t seq, bool heartbeat_alive, guard_decision_t *out)
{
    if (g->state != PROTO_BOARD_STATE_HOLD) {
        verdict(out, seq, PROTO_RESULT_REJECTED, PROTO_RULE_MODE, PROTO_REASON_NOT_IN_HOLD);
        return;
    }
    if (!heartbeat_alive) {
        verdict(out, seq, PROTO_RESULT_REJECTED, PROTO_RULE_MODE, PROTO_REASON_NO_HEARTBEAT);
        return;
    }
    verdict(out, seq, PROTO_RESULT_ACCEPTED, PROTO_RULE_NONE, PROTO_REASON_NONE);
    g->state = PROTO_BOARD_STATE_NORMAL;
    g->reject_streak = 0u;
}

bool guard_velocity(const guard_t *g, const proto_velocity_cmd_t *cmd, proto_drive_t *out)
{
    if (g->state == PROTO_BOARD_STATE_HOLD) {
        return false;
    }
    out->v_mm_s = cmd->v_mm_s;
    out->w_mrad_s = cmd->w_mrad_s;
    return true;
}

void guard_heartbeat_lost(guard_t *g)
{
    g->state = PROTO_BOARD_STATE_HOLD;
}

bool guard_telemetry(guard_t *g, const site_t *s, const proto_telemetry_t *tel,
                     bool heartbeat_alive, proto_goal_t *goal)
{
    geo_point_t pos = { tel->x_cm, tel->y_cm };
    if (g->state == PROTO_BOARD_STATE_RECOVERY) {
        if (recovery_arrived(pos, g->recovery_goal)) {
            g->state = PROTO_BOARD_STATE_HOLD;
        }
        return false;
    }
    if (g->state != PROTO_BOARD_STATE_NORMAL || !heartbeat_alive ||
        geofence_check(&s->fence, pos) == GEOFENCE_OK) {
        return false;
    }
    enter_recovery(g, site_nearest_safe(s, pos), PROTO_GOAL_SOURCE_RECOVERY_SAFE, goal);
    return true;
}

void guard_tick(guard_t *g, uint32_t now_ms, uint32_t telemetry_age_ms)
{
    if (g->state != PROTO_BOARD_STATE_RECOVERY) {
        return;
    }
    if (!g->recovery_timed) {
        g->recovery_timed = true;
        g->recovery_t0_ms = now_ms;
    }
    if (telemetry_age_ms > RECOVERY_TELEMETRY_TIMEOUT_MS ||
        now_ms - g->recovery_t0_ms > RECOVERY_TIMEOUT_MS) {
        g->state = PROTO_BOARD_STATE_HOLD;
    }
}
