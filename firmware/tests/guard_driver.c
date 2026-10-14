/* Kartın karar katmanını (firmware/app/guard/) PC'de çalıştıran sürücü.
 * test_guard.py bunu gcc ile derler ve komut yollar.
 *
 * Harita kartınkinden bağımsız, testin kendi verisi: kartın verisi Faz 3'te
 * değişecek, kararın mantığı değişmeyecek.
 *
 * Her satır bir komut, her komuta bir satır cevap. Sayılar ondalık.
 *   init                       → "ok"
 *   goto <seq> <x> <y> <yaw> [canlı 0|1]  → karar (canlı verilmezse 1)
 *   reset <seq> <canlı 0|1>    → karar
 *   wait <seq> <süre_s>        → karar
 *   stop <seq>                 → karar
 *   takehalt                   → "1" HOLD'a girildi, araca HALT(0) gidecek; "0" değil
 *   fresh <seq> <tip> <now> <ts> → "1" taze; "0 -" bayat, cevap yok; "0 " + karar satırı
 *   lost                       → "ok" (kalp atışı zaman aşımı)
 *   vel <v> <w>                → "v,w" araca giden DRIVE (kırpıldıysa sonunda " c") ya da "-"
 *   speed <seq> <mm_s> [canlı] → karar (hiz_siniri)
 *   nearest <0|1> <x> <y>      → "<x> <y>"; 0: güvenli noktasız harita
 *   tel <x> <y> <canlı 0|1>    → "<goal|-> <state>" (araç konumu, TELEMETRY)
 *   tick <now_ms> <tel_yaşı_ms> → "<state>" (her döngüdeki zaman denetimi)
 * Karar satırı:
 *   <ref_seq> <result> <rule> <reason> <hint_x> <hint_y> <goal|-> <state> <streak> <halt|->
 *   <speed|-> <value> <lo> <hi>
 *   goal: "x,y,yaw,source" ya da hedef gönderilmiyorsa "-"; halt: HALT'ın süresi ya da "-";
 *   speed: SPEED_LIMIT_SET değeri ya da "-"; value/lo/hi: VERDICT'in alanları */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "guard/guard.h"

static const site_t test_site = {
    .fence = {
        .allowed = { .n = 4, .v = { {-2000, -2000}, {2000, -2000}, {2000, 2000}, {-2000, 2000} } },
        .n_forbidden = 1,
        .forbidden = { { .n = 4, .v = { {500, 500}, {900, 500}, {900, 900}, {500, 900} } } },
    },
    .home = {-100, -100},
    .n_safe = 3,
    /* (0, 1000) ile (0, -1000) orijine eşit uzaklıkta: eşitlikte ilki seçilmeli */
    .safe = { {0, 1000}, {0, -1000}, {1500, 1500} },
};

static const site_t no_safe_site = {
    .fence = test_site.fence,
    .home = {-100, -100},
    .n_safe = 0,
};

static guard_t g;

static void print_decision(const guard_decision_t *d)
{
    printf("%lu %u %u %u %d %d ", (unsigned long)d->verdict.ref_seq, d->verdict.result,
           d->verdict.rule, d->verdict.reason, d->verdict.hint_x_cm, d->verdict.hint_y_cm);
    if (d->send_goal) {
        printf("%d,%d,%d,%u", d->goal.x_cm, d->goal.y_cm, d->goal.yaw_mrad, d->goal.source);
    } else {
        printf("-");
    }
    printf(" %u %u ", g.state, g.reject_streak);
    if (d->send_halt) {
        printf("%u ", d->halt.duration_s);
    } else {
        printf("- ");
    }
    if (d->send_speed_limit) {
        printf("%u ", d->speed_limit.limit_mm_s);
    } else {
        printf("- ");
    }
    printf("%ld %ld %ld\n", (long)d->verdict.value, (long)d->verdict.lo, (long)d->verdict.hi);
}

int main(void)
{
    static char line[256];
    guard_init(&g);
    while (fgets(line, sizeof line, stdin) != NULL) {
        guard_decision_t d;
        unsigned long seq, now, ts;
        int x, y, yaw, alive, which;
        if (strncmp(line, "init", 4) == 0) {
            guard_init(&g);
            puts("ok");
        } else if (sscanf(line, "goto %lu %d %d %d %d", &seq, &x, &y, &yaw, &alive) >= 4) {
            if (sscanf(line, "goto %lu %d %d %d %d", &seq, &x, &y, &yaw, &alive) == 4) {
                alive = 1;
            }
            proto_goto_cmd_t cmd = { .goal_x_cm = (int16_t)x, .goal_y_cm = (int16_t)y,
                                     .goal_yaw_mrad = (int16_t)yaw };
            guard_goto(&g, &test_site, (uint32_t)seq, alive != 0, &cmd, &d);
            print_decision(&d);
        } else if (sscanf(line, "reset %lu %d", &seq, &alive) == 2) {
            guard_reset(&g, (uint32_t)seq, alive != 0, &d);
            print_decision(&d);
        } else if (sscanf(line, "vel %d %d", &x, &y) == 2) {
            proto_velocity_cmd_t cmd = { .v_mm_s = (int16_t)x, .w_mrad_s = (int16_t)y };
            proto_drive_t drive;
            bool clipped = false;
            if (guard_velocity(&g, &cmd, &drive, &clipped)) {
                printf("%d,%d%s\n", drive.v_mm_s, drive.w_mrad_s, clipped ? " c" : "");
            } else {
                puts("-");
            }
        } else if (sscanf(line, "tel %d %d %d", &x, &y, &alive) == 3) {
            proto_telemetry_t tel = { .x_cm = (int16_t)x, .y_cm = (int16_t)y, .yaw_mrad = 0 };
            proto_goal_t goal;
            if (guard_telemetry(&g, &test_site, &tel, alive != 0, &goal)) {
                printf("%d,%d,%d,%u %u\n", goal.x_cm, goal.y_cm, goal.yaw_mrad, goal.source, g.state);
            } else {
                printf("- %u\n", g.state);
            }
        } else if (sscanf(line, "tick %lu %d", &seq, &x) == 2) {
            guard_tick(&g, (uint32_t)seq, (uint32_t)x);
            printf("%u\n", g.state);
        } else if (sscanf(line, "speed %lu %d %d", &seq, &x, &alive) >= 2) {
            if (sscanf(line, "speed %lu %d %d", &seq, &x, &alive) == 2) {
                alive = 1;
            }
            proto_speed_limit_cmd_t cmd = { .limit_mm_s = (uint16_t)x };
            guard_speed_limit(&g, &test_site, (uint32_t)seq, alive != 0, &cmd, &d);
            print_decision(&d);
        } else if (sscanf(line, "wait %lu %d", &seq, &x) == 2) {
            proto_wait_cmd_t cmd = { .duration_s = (uint16_t)x };
            guard_wait(&g, (uint32_t)seq, &cmd, &d);
            print_decision(&d);
        } else if (sscanf(line, "stop %lu", &seq) == 1) {
            guard_stop(&g, (uint32_t)seq, &d);
            print_decision(&d);
        } else if (sscanf(line, "fresh %lu %d %lu %lu", &seq, &x, &now, &ts) == 4) {
            bool reply;
            if (guard_fresh((uint32_t)seq, (uint8_t)x, (uint32_t)now, (uint32_t)ts, &d, &reply)) {
                puts("1");
            } else if (!reply) {
                puts("0 -");
            } else {
                printf("0 ");
                print_decision(&d);
            }
        } else if (strncmp(line, "takehalt", 8) == 0) {
            puts(guard_take_halt(&g) ? "1" : "0");
        } else if (strncmp(line, "lost", 4) == 0) {
            guard_heartbeat_lost(&g);
            puts("ok");
        } else if (sscanf(line, "nearest %d %d %d", &which, &x, &y) == 3) {
            geo_point_t p = { (int16_t)x, (int16_t)y };
            geo_point_t n = site_nearest_safe(which ? &test_site : &no_safe_site, p);
            printf("%d %d\n", n.x_cm, n.y_cm);
        } else {
            puts("ERR");
        }
        fflush(stdout);
    }
    return 0;
}
