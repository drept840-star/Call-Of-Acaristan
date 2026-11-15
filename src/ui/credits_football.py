"""Credits background football match (Biribel vs Bodi): simulation, animations and 3D pitch."""
from __future__ import annotations

import math
import random
import traceback

import pygame

from core.config import HEIGHT, WIDTH
from core.state import STATE


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _smooth(v):
    v = _clamp(v, 0.0, 1.0)
    return v * v * (3.0 - 2.0 * v)


def _turn_toward(cur, target, max_step):
    diff = (target - cur + 180.0) % 360.0 - 180.0
    if abs(diff) <= max_step:
        return target % 360.0
    return (cur + math.copysign(max_step, diff)) % 360.0


def _orthonormalize(m):
    from engine3d.core import v_cross, v_norm

    r0 = v_norm((m[0], m[1], m[2]))
    r2 = v_norm(v_cross(r0, (m[3], m[4], m[5])))
    r1 = v_cross(r2, r0)
    return (r0[0], r0[1], r0[2], r1[0], r1[1], r1[2], r2[0], r2[1], r2[2])


_LR_PAIRS = (
    ("lsh_p", "rsh_p"),
    ("lsh_r", "rsh_r"),
    ("lsh_y", "rsh_y"),
    ("lel", "rel"),
    ("lhip_p", "rhip_p"),
    ("lhip_r", "rhip_r"),
    ("lkn", "rkn"),
    ("lank", "rank"),
)
_SIGN_FLIP = ("spine_r", "twist", "body_r", "head_y", "head_x")


def _mirror_lr(pose):
    out = dict(pose)
    for lk, rk in _LR_PAIRS:
        # Authored poses often set one side only (e.g. rsh_y); the missing joint is neutral.
        if lk in pose or rk in pose:
            out[lk], out[rk] = pose.get(rk, 0.0), pose.get(lk, 0.0)
    for sk in _SIGN_FLIP:
        if sk in out:
            out[sk] = -out[sk]
    return out


class _FootballSim:
    """Continuous 2-player pasture kickabout (Biribel vs Bodi) behind the credits."""

    PITCH_HX = 7.2
    PITCH_HZ = 4.8
    GOAL_HW = 2.04
    GOAL_H = 1.87
    GOAL_D = 1.38
    BALL_R = 0.145
    MAX_PUFFS = 28

    _CELEBRATIONS = ("knee_slide", "aeroplane", "fist_pump", "banter")

    def __init__(self, seed=None):
        self._seed = seed
        self._rng = random.Random(seed)
        self.reset()

    def reset(self):
        if self._seed is not None:
            self._rng = random.Random(self._seed)
        self.t = 0.0
        self.ball_pos = [0.0, self.BALL_R, 0.0]
        self.ball_vel = [0.0, 0.0, 0.0]
        self.ball_spin_y = 0.0
        self.ball_mat = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
        self._renorm_n = 0

        rng = self._rng
        bx0, bz0 = rng.uniform(-2.6, -0.8), rng.uniform(-1.8, 1.8)
        dx0, dz0 = rng.uniform(0.8, 2.6), rng.uniform(-1.8, 1.8)
        self.players = {
            "biribel": self._make_player(bx0, bz0, math.degrees(math.atan2(-bx0, -bz0))),
            "bodi": self._make_player(dx0, dz0, math.degrees(math.atan2(-dx0, -dz0))),
        }
        self.turn = rng.choice(("biribel", "bodi"))
        self.mode = "rally"       # "rally" -> "shot" -> "goal"
        self.rally_passes = 0
        self.target_passes = rng.randint(1, 2)
        self.dribble_left = rng.randint(0, 2)
        self._dribble_dir = rng.choice((-1.0, 1.0))
        self._press_mode = rng.random() < 0.55
        self._last_celeb = None
        self.kick_count = 0
        self.shot_t = 0.0
        self.goal_t = 0.0
        self.goal_count = 0
        self.scorer = None
        self.cooldown = 0.0
        self.slide_cd = rng.uniform(2.0, 5.0)
        self.feint_cd = rng.uniform(1.5, 4.0)
        self.breather_cd = rng.uniform(5.0, 10.0)
        self.stall_t = 0.0
        self.clang_t = 0.0
        self.cam_x = 0.0
        self.tgt_x = 0.0
        self.tgt_z = 0.0
        self.cam_d = 7.0
        self.cam_fov = 50.0
        self.puffs = []           # [x, y, z, vx, vy, vz, age, life, tier, col_idx]
        self._puff_acc = 0.0
        for pname, pl in self.players.items():
            pl["pose"] = dict(self._compute_pose(pname))

    @staticmethod
    def _make_player(x, z, yaw):
        return {
            "pos": [x, z],
            "vel": [0.0, 0.0],
            "yaw": yaw,
            "yaw_vel": 0.0,
            "gait": 0.0,
            "backpedal": 0.0,
            "jockey": 0.0,
            "action": None,
            "action_t": 0.0,
            "action_dur": 0.4,
            "action_hit": 0.18,
            "action_pending": False,
            "action_foot": "r",
            "action_subtype": "pass",
            "action_meta": {},
            "beckon_t": 0.0,
            "touch_grace": 0.0,
            "pose": None,
            "trans_pose": None,
            "trans_t": 0.0,
            "trans_dur": 0.1,
            "expr": "smile",
            "mouth": 0.0,
        }

    def _spawn_puff(self, x, y, z, count=3, spread=1.1, col_idx=0, tier=1, vy_base=0.75):
        # col_idx: 0 dirt, 1 grass, 2 chalk/spark
        for i in range(count):
            ang = self.t * 19.3 + i * (math.tau / max(1, count))
            spd = spread * (0.45 + 0.55 * ((i * 37) % 10) / 10.0)
            self.puffs.append([
                x + math.cos(ang) * 0.06,
                max(0.03, y),
                z + math.sin(ang) * 0.06,
                math.cos(ang) * spd,
                vy_base + 0.45 * ((i * 13) % 5) / 5.0,
                math.sin(ang) * spd,
                0.0,
                0.38 + 0.12 * (i % 3),
                min(3, max(0, tier)),
                col_idx,
            ])
        if len(self.puffs) > self.MAX_PUFFS:
            del self.puffs[: len(self.puffs) - self.MAX_PUFFS]

    def _step_puffs(self, dt):
        kept = []
        for pf in self.puffs:
            pf[6] += dt
            if pf[6] >= pf[7]:
                continue
            pf[4] -= 3.2 * dt
            pf[0] += pf[3] * dt
            pf[1] = max(0.02, pf[1] + pf[4] * dt)
            pf[2] += pf[5] * dt
            pf[3] *= math.exp(-3.0 * dt)
            pf[5] *= math.exp(-3.0 * dt)
            kept.append(pf)
        self.puffs = kept

    @staticmethod
    def _dist_point_seg_xz(px, pz, ax, az, bx, bz):
        abx, abz = bx - ax, bz - az
        len2 = abx * abx + abz * abz
        if len2 <= 1e-8:
            return math.hypot(px - ax, pz - az)
        u = _clamp(((px - ax) * abx + (pz - az) * abz) / len2, 0.0, 1.0)
        cx, cz = ax + u * abx, az + u * abz
        return math.hypot(px - cx, pz - cz)

    @staticmethod
    def _pick_foot(p, bx, bz):
        rad = math.radians(p["yaw"])
        # Character right vector in (x, z) when facing yaw (0 = +Z, +90 = +X)
        rx, rz = math.cos(rad), -math.sin(rad)
        side = (bx - p["pos"][0]) * rx + (bz - p["pos"][1]) * rz
        return "l" if side < -0.04 else "r"

    def _reroll_possession(self):
        rng = self._rng
        self.rally_passes = 0
        self.target_passes = rng.randint(1, 2)
        self.dribble_left = rng.randint(0, 2)
        self._dribble_dir = rng.choice((-1.0, 1.0))
        self._press_mode = rng.random() < 0.55

    def _pick_shot_target(self, goal_x, atk_dir, bx, bz, dfn_z=None):
        rng = self._rng
        kx = goal_x + atk_dir * 0.90
        if dfn_z is not None and rng.random() < 0.78:
            side = -1.0 if dfn_z >= 0.0 else 1.0
        else:
            side = rng.choice((-1.0, 1.0))
        roll = rng.random()
        if roll < 0.50:
            # Driven low/mid corner strike
            kz = side * rng.uniform(0.85, 1.88)
            dist_g = math.hypot(kx - bx, kz - bz)
            kspeed = _clamp(dist_g * 1.55 + rng.uniform(1.0, 2.4), 9.8, 12.6)
            kloft = rng.uniform(1.3, 2.6)
            kcurl = rng.uniform(-2.4, 2.4)
        elif roll < 0.88:
            # Lofted top-corner curler
            kz = side * rng.uniform(1.10, 1.92)
            dist_g = math.hypot(kx - bx, kz - bz)
            kspeed = _clamp(dist_g * 1.45 + rng.uniform(0.6, 1.8), 9.2, 11.8)
            kloft = rng.uniform(3.2, 4.3)
            kcurl = -side * rng.uniform(1.4, 2.6)
        else:
            # Post-skimmer / narrow miss
            kz = side * rng.uniform(1.96, 2.42)
            dist_g = math.hypot(kx - bx, kz - bz)
            kspeed = _clamp(dist_g * 1.50 + rng.uniform(0.8, 2.0), 9.4, 12.2)
            kloft = rng.uniform(1.8, 3.4)
            kcurl = rng.uniform(-1.8, 1.8)
        return kx, kz, kspeed, kloft, kcurl

    def _start_action(self, p, action, dur, hit=0.0, foot="r", subtype="", expr="smile", **meta):
        p["action"] = action
        p["action_t"] = 0.0
        p["action_dur"] = dur
        p["action_hit"] = hit
        p["action_pending"] = hit > 0.0 or action in ("dive", "slide")
        p["action_foot"] = foot
        p["action_subtype"] = subtype
        p["action_meta"] = meta
        p["expr"] = expr
        p["beckon_t"] = 0.0

    def _kick_ball(self, p, tx, tz, speed, loft, kind, curl=0.0, hit_override=None):
        bx, _by, bz = self.ball_pos
        foot = self._pick_foot(p, bx, bz)
        if kind == "dribble":
            dur, hit, expr, ratio = 0.28, 0.11, "smile", 0.393
        elif kind == "shot":
            dur, hit, expr, ratio = 0.48, 0.20, "stern", 0.417
        elif kind == "lob":
            dur, hit, expr, ratio = 0.44, 0.19, "smile", 0.432
        elif kind == "backheel":
            dur, hit, expr, ratio = 0.42, 0.18, "grin", 0.429
        else:
            dur, hit, expr, ratio = 0.40, 0.17, "smile", 0.425
        if hit_override is not None:
            hit = _clamp(hit_override, 0.13, 0.22)
            dur = max(0.38, hit / ratio)
        self._start_action(
            p,
            "dribble" if kind == "dribble" else "kick",
            dur,
            hit=hit,
            foot=foot,
            subtype=kind,
            expr=expr,
            target=(tx, tz, speed, loft, curl),
            target_y=self.ball_pos[1],
        )
        self.cooldown = 0.34 if kind == "dribble" else 0.38
        self.stall_t = 0.0

    def _execute_action_hit(self, name, p):
        act = p["action"]
        other = "bodi" if name == "biribel" else "biribel"
        bx, by, bz = self.ball_pos
        px, pz = p["pos"]
        if act in ("kick", "dribble"):
            max_d = 0.85 if act == "dribble" else 0.96
            if math.hypot(bx - px, bz - pz) > max_d or by > 1.25:
                return
            tx, tz, speed, loft, curl = p["action_meta"]["target"]
            p["action_meta"]["contact_pos"] = (bx, by, bz)
            p["action_meta"]["target_y"] = by
            p["touch_grace"] = 0.24
            dx, dz = tx - bx, tz - bz
            d = math.hypot(dx, dz) or 1.0
            self.ball_vel = [dx / d * speed, loft, dz / d * speed]
            self.ball_spin_y = curl
            if p["action_subtype"] == "shot":
                self.mode = "shot"
                self.shot_t = 0.0
                self._spawn_puff(bx, 0.04, bz, count=4, spread=1.6, col_idx=0, tier=2)
                self._spawn_puff(bx, 0.04, bz, count=2, spread=1.4, col_idx=1, tier=1)
            elif p["action_subtype"] == "lob":
                self.turn = other
                self.rally_passes += 1
                self._reroll_possession()
                self.rally_passes = max(1, self.rally_passes)
                self._spawn_puff(bx, 0.04, bz, count=2, spread=1.0, col_idx=1, tier=1)
            elif act == "dribble":
                self.dribble_left -= 1
                if self._rng.random() < 0.45:
                    self._dribble_dir = -self._dribble_dir
                self._spawn_puff(bx, 0.03, bz, count=1, spread=0.6, col_idx=1, tier=0)
            else:
                self.turn = other
                next_passes = self.rally_passes + 1
                self._reroll_possession()
                self.rally_passes = next_passes
            self.kick_count += 1
        elif act == "header":
            if math.hypot(bx - px, bz - pz) > 0.85 or by < 0.62 or by > 1.85:
                return
            p["action_meta"]["contact_pos"] = (bx, by, bz)
            p["action_meta"]["target_y"] = by
            p["touch_grace"] = 0.28
            tx, tz, speed, loft = p["action_meta"]["target"]
            dx, dz = tx - bx, tz - bz
            d = math.hypot(dx, dz) or 1.0
            self.ball_vel = [dx / d * speed, loft, dz / d * speed]
            self.ball_spin_y = 0.8 if (self.kick_count % 2) else -0.8
            self._spawn_puff(bx, by, bz, count=2, spread=0.9, col_idx=2, tier=1, vy_base=0.2)
            if p["action_meta"].get("is_shot"):
                self.mode = "shot"
                self.shot_t = 0.0
            else:
                self.turn = other
                self.rally_passes += 1
                self.dribble_left = self._rng.randint(0, 2)
            self.kick_count += 1
        elif act == "chest":
            if math.hypot(bx - px, bz - pz) > 0.80 or by < 0.40 or by > 1.48:
                return
            p["action_meta"]["contact_pos"] = (bx, by, bz)
            p["action_meta"]["target_y"] = by
            p["touch_grace"] = 0.26
            rad = math.radians(p["yaw"])
            self.ball_vel = [
                math.sin(rad) * 1.65 + p["vel"][0] * 0.25,
                0.28,
                math.cos(rad) * 1.65 + p["vel"][1] * 0.25,
            ]
            self.ball_spin_y *= 0.2
            self.turn = name
            self.dribble_left = self._rng.randint(0, 1)
            self.cooldown = 0.20
        elif act == "trap":
            if math.hypot(bx - px, bz - pz) > 0.78 or by > 1.10:
                return
            p["action_meta"]["contact_pos"] = (bx, by, bz)
            p["action_meta"]["target_y"] = by
            p["touch_grace"] = 0.24
            rad = math.radians(p["yaw"])
            self.ball_pos[1] = max(self.BALL_R, min(by, 0.34))
            self.ball_vel = [
                math.sin(rad) * 1.55 + p["vel"][0] * 0.35,
                0.08,
                math.cos(rad) * 1.55 + p["vel"][1] * 0.35,
            ]
            self.ball_spin_y *= 0.1
            self._spawn_puff(bx, 0.03, bz, count=1, spread=0.6, col_idx=1, tier=0)
            self.turn = name
            self.dribble_left = self._rng.randint(0, 1)
            self.cooldown = 0.16
        elif act == "parry":
            if math.hypot(bx - px, bz - pz) > 1.05 or by > 1.65:
                return
            p["action_meta"]["contact_pos"] = (bx, by, bz)
            p["action_meta"]["target_y"] = by
            p["touch_grace"] = 0.26
            atk_dir = -1.0 if px < 0.0 else 1.0
            self.ball_vel = [
                -atk_dir * self._rng.uniform(2.8, 4.4),
                self._rng.uniform(0.85, 1.75),
                _clamp((bz - pz) * 2.4 + self._rng.uniform(-0.8, 0.8), -2.5, 2.5),
            ]
            self._spawn_puff(bx, by, bz, count=3, spread=1.3, col_idx=2, tier=1)
            self.turn = name
            self.mode = "rally"
            self._reroll_possession()
            self.cooldown = 0.28

    def _step_ball_sample(self, bx, by, bz, vx, vy, vz, spin_y, dt_s):
        r = self.BALL_R
        on_ground = by <= r + 0.008 and abs(vy) < 0.35
        if on_ground:
            by = r
            vy = 0.0
            damp = math.exp(-1.45 * dt_s)
            vx *= damp
            vz *= damp
            spin_y *= math.exp(-2.8 * dt_s)
        else:
            vy -= 13.5 * dt_s
            air_damp = math.exp(-0.22 * dt_s)
            vx *= air_damp
            vz *= air_damp
            if abs(spin_y) > 0.05:
                vx += -vz * spin_y * 0.11 * dt_s
                vz += vx * spin_y * 0.11 * dt_s
            spin_y *= math.exp(-0.4 * dt_s)
        bx += vx * dt_s
        by += vy * dt_s
        bz += vz * dt_s
        if by < r:
            by = r
            if vy < -0.95:
                vy = -vy * 0.56
                vx *= 0.88
                vz *= 0.88
            else:
                vy = 0.0
        return bx, by, bz, vx, vy, vz, spin_y

    def _ball_samples(self, horizon=0.72, step=0.045):
        bx, by, bz = self.ball_pos
        vx, vy, vz = self.ball_vel
        spin = self.ball_spin_y
        samples = []
        t = 0.0
        while t < horizon - 1e-6:
            t += step
            bx, by, bz, vx, vy, vz, spin = self._step_ball_sample(bx, by, bz, vx, vy, vz, spin, step)
            bx = _clamp(bx, -self.PITCH_HX - 1.5, self.PITCH_HX + 1.5)
            bz = _clamp(bz, -self.PITCH_HZ - 0.9, self.PITCH_HZ + 0.9)
            samples.append((t, bx, by, bz, vx, vy, vz))
        return samples

    @staticmethod
    def _intercept_target(px, pz, max_spd, samples):
        best = samples[-1]
        best_gap = 1e9
        for s in samples:
            t_s, sx, _sy, sz, *_ = s
            t_reach = max(0.0, (math.hypot(sx - px, sz - pz) - 0.34) / max(0.5, max_spd))
            if t_reach <= t_s:
                return sx, sz, t_s
            gap = t_reach - t_s
            if gap < best_gap:
                best_gap = gap
                best = s
        return best[1], best[3], best[0]

    def _predict_arrival(self, name, samples, max_t=0.24):
        p = self.players[name]
        px, pz = p["pos"]
        pvx, pvz = p["vel"]
        bx0, _by0, bz0 = self.ball_pos
        cur_d = math.hypot(bx0 - px, bz0 - pz)
        if cur_d > 2.25:
            return None
        vx0, _vy0, vz0 = self.ball_vel
        if math.hypot(vx0, vz0) < 1.35:
            return None
        best = None
        best_d = 0.68
        for t_s, sx, sy, sz, svx, svy, svz in samples:
            if t_s > max_t:
                break
            pred_px = px + pvx * min(t_s, 0.14)
            pred_pz = pz + pvz * min(t_s, 0.14)
            d = math.hypot(sx - pred_px, sz - pred_pz)
            if d < best_d:
                best_d = d
                best = (t_s, sx, sy, sz, math.hypot(svx, svz), svy)
        return best

    def _predict_shot_plane(self, goal_x, atk_dir):
        bx, by, bz = self.ball_pos
        vx, vy, vz = self.ball_vel
        spin = self.ball_spin_y
        plane_x = goal_x - atk_dir * 0.70
        if (plane_x - bx) * atk_dir <= 0.0:
            return _clamp(bz, -1.85, 1.85), _clamp(by, self.BALL_R, self.GOAL_H), 0.0
        step = 0.025
        t = 0.0
        for _ in range(44):
            prev_x, prev_y, prev_z = bx, by, bz
            bx, by, bz, vx, vy, vz, spin = self._step_ball_sample(bx, by, bz, vx, vy, vz, spin, step)
            t += step
            if (bx - plane_x) * atk_dir >= 0.0:
                denom = (bx - prev_x)
                q = _clamp((plane_x - prev_x) / denom, 0.0, 1.0) if abs(denom) > 1e-6 else 1.0
                cz = prev_z + (bz - prev_z) * q
                cy = prev_y + (by - prev_y) * q
                return _clamp(cz, -1.88, 1.88), _clamp(cy, self.BALL_R, self.GOAL_H + 0.1), t - step * (1.0 - q)
        return _clamp(bz, -1.85, 1.85), _clamp(by, self.BALL_R, self.GOAL_H), t

    def _step_ball(self, dt):
        from engine3d.core import m_mul, rot_x, rot_y, rot_z

        sub_dt = dt * 0.5
        r = self.BALL_R
        for _ in range(2):
            bx, by, bz = self.ball_pos
            vx, vy, vz = self.ball_vel
            on_ground = by <= r + 0.008 and abs(vy) < 0.35
            if on_ground:
                by = r
                vy = 0.0
                damp = math.exp(-1.45 * sub_dt)
                vx *= damp
                vz *= damp
                self.ball_spin_y *= math.exp(-2.8 * sub_dt)
                if math.hypot(vx, vz) < 0.04:
                    vx = vz = 0.0
            else:
                vy -= 13.5 * sub_dt
                air_damp = math.exp(-0.22 * sub_dt)
                vx *= air_damp
                vz *= air_damp
                # Subtle Magnus curve in flight
                if abs(self.ball_spin_y) > 0.05:
                    vx += -vz * self.ball_spin_y * 0.11 * sub_dt
                    vz += vx * self.ball_spin_y * 0.11 * sub_dt
                self.ball_spin_y *= math.exp(-0.4 * sub_dt)

            bx += vx * sub_dt
            by += vy * sub_dt
            bz += vz * sub_dt

            if by < r:
                by = r
                if vy < -0.95:
                    if vy < -2.6:
                        self._spawn_puff(bx, 0.03, bz, count=2, spread=0.8, col_idx=0, tier=1, vy_base=0.4)
                    vy = -vy * 0.56
                    vx *= 0.88
                    vz *= 0.88
                else:
                    vy = 0.0

            # Roll & spin rotation matching travel.
            dx = vx * sub_dt
            dz = vz * sub_dt
            if abs(dx) > 1e-5 or abs(dz) > 1e-5:
                ax_deg = math.degrees(dx / r)
                az_deg = math.degrees(dz / r)
                self.ball_mat = m_mul(rot_x(az_deg), m_mul(rot_z(-ax_deg), self.ball_mat))
            if abs(self.ball_spin_y) > 0.05 and not on_ground:
                self.ball_mat = m_mul(rot_y(math.degrees(self.ball_spin_y * sub_dt)), self.ball_mat)

            # Goalposts, crossbar & net collisions (both goals at +-PITCH_HX).
            post_hit_r = r + 0.065
            clang_hit = False
            for side in (-1.0, 1.0):
                gx = side * self.PITCH_HX
                # Upright posts
                if by < self.GOAL_H + 0.14:
                    for pz in (-self.GOAL_HW, self.GOAL_HW):
                        px_d, pz_d = bx - gx, bz - pz
                        dist = math.hypot(px_d, pz_d)
                        if 1e-6 < dist < post_hit_r:
                            nx, nz = px_d / dist, pz_d / dist
                            bx = gx + nx * post_hit_r
                            bz = pz + nz * post_hit_r
                            vn = vx * nx + vz * nz
                            if vn < 0.0:
                                if vn < -1.8:
                                    clang_hit = True
                                vx -= 1.75 * vn * nx
                                vz -= 1.75 * vn * nz
                # Crossbar
                if abs(bz) <= self.GOAL_HW + 0.06:
                    px_d, py_d = bx - gx, by - self.GOAL_H
                    dist = math.hypot(px_d, py_d)
                    if 1e-6 < dist < post_hit_r:
                        nx, ny = px_d / dist, py_d / dist
                        bx = gx + nx * post_hit_r
                        by = self.GOAL_H + ny * post_hit_r
                        vn = vx * nx + vy * ny
                        if vn < 0.0:
                            if vn < -1.8:
                                clang_hit = True
                            vx -= 1.75 * vn * nx
                            vy -= 1.75 * vn * ny

                # Inside goal net
                if side * bx > self.PITCH_HX and abs(bz) < self.GOAL_HW - 0.03 and by < self.GOAL_H + 0.05:
                    back_x = gx + side * (self.GOAL_D - r)
                    if side * bx > side * back_x:
                        bx = back_x
                        if side * vx > 0.0:
                            vx = -vx * 0.16
                        vy *= 0.45
                        vz *= 0.45
                    if abs(bz) > self.GOAL_HW - r:
                        bz = math.copysign(self.GOAL_HW - r, bz)
                        vz = -vz * 0.18
                        vx *= 0.45
                    if by > self.GOAL_H - r:
                        by = self.GOAL_H - r
                        if vy > 0.0:
                            vy = -vy * 0.2
                    # Goal scored!
                    if self.mode in ("rally", "shot") and side * bx > self.PITCH_HX + r * 0.5:
                        self.mode = "goal"
                        self.goal_t = 0.0
                        self.goal_count += 1
                        self.scorer = "biribel" if side > 0 else "bodi"
                        other = "bodi" if self.scorer == "biribel" else "biribel"
                        style = self._rng.choice([c for c in self._CELEBRATIONS if c != self._last_celeb])
                        self._last_celeb = style
                        dur = 1.85 if style in ("knee_slide", "aeroplane") else 1.70
                        self._start_action(
                            self.players[self.scorer],
                            "celebrate",
                            dur,
                            subtype=style,
                            expr="grin",
                            other=other,
                        )
                        self._start_action(
                            self.players[other],
                            "disbelief",
                            0.72,
                            expr="surprised",
                        )

                # Outside side/back net prevents ghosting into net from outside
                if (
                    side * bx > self.PITCH_HX + 0.04
                    and side * bx < self.PITCH_HX + self.GOAL_D + r
                    and by < self.GOAL_H + 0.05
                ):
                    if self.GOAL_HW <= abs(bz) < self.GOAL_HW + r + 0.05:
                        bz = math.copysign(self.GOAL_HW + r + 0.05, bz)
                        vz = math.copysign(abs(vz) * 0.25, bz)
                    elif abs(bz) < self.GOAL_HW and side * bx > self.PITCH_HX + self.GOAL_D - 0.05 and side * vx < 0.0:
                        bx = gx + side * (self.GOAL_D + r + 0.05)
                        vx = side * abs(vx) * 0.25

            if clang_hit and self.clang_t <= 0.0:
                self.clang_t = 0.22
                self._spawn_puff(bx, by, bz, count=4, spread=1.5, col_idx=2, tier=2, vy_base=0.6)
                shooter = self.players[self.turn]
                if shooter["action"] is None:
                    self._start_action(shooter, "disbelief", 0.78, expr="surprised")

            # Soft pitch perimeter outside goal mouths so balls stay playable.
            if abs(bz) > self.PITCH_HZ + 1.2:
                bz = math.copysign(self.PITCH_HZ + 1.2, bz)
                vz = -vz * 0.35
            # Also catch balls skied over the crossbar through the goal mouth.
            if abs(bx) > self.PITCH_HX + 1.9 and (abs(bz) >= self.GOAL_HW - 0.03 or by >= self.GOAL_H + 0.05):
                bx = math.copysign(self.PITCH_HX + 1.9, bx)
                vx = -vx * 0.35

            self.ball_pos = [bx, by, bz]
            self.ball_vel = [vx, vy, vz]

        self._renorm_n += 1
        if self._renorm_n >= 45:
            self._renorm_n = 0
            self.ball_mat = _orthonormalize(self.ball_mat)

    def _steer_player(self, name, tx, tz, max_spd, look_pos, dt):
        p = self.players[name]
        px, pz = p["pos"]
        act = p["action"]
        old_yaw = p["yaw"]

        if act == "dive":
            u = p["action_t"] / p["action_dur"]
            dyaw = p["action_meta"].get("dive_yaw", p["yaw"])
            p["yaw"] = _turn_toward(p["yaw"], dyaw, 720.0 * dt)
            rad = math.radians(dyaw)
            burst = 6.4 * max(0.0, 1.0 - u / 0.52) if u < 0.52 else 0.0
            p["vel"][0] = math.sin(rad) * burst
            p["vel"][1] = math.cos(rad) * burst
            p["backpedal"] = 0.0
            p["jockey"] = 0.0
        elif act == "slide":
            u = p["action_t"] / p["action_dur"]
            syaw = p["action_meta"].get("slide_yaw", p["yaw"])
            p["yaw"] = _turn_toward(p["yaw"], syaw, 680.0 * dt)
            rad = math.radians(syaw)
            burst = 5.1 * max(0.0, 1.0 - u / 0.54) if u < 0.54 else 0.0
            p["vel"][0] = math.sin(rad) * burst
            p["vel"][1] = math.cos(rad) * burst
            p["backpedal"] = 0.0
            p["jockey"] = 0.0
        elif act == "celebrate" and p["action_subtype"] == "knee_slide":
            u = p["action_t"] / p["action_dur"]
            syaw = p["action_meta"].get("slide_yaw", p["yaw"])
            p["yaw"] = _turn_toward(p["yaw"], syaw, 320.0 * dt)
            rad = math.radians(syaw)
            if u < 0.28:
                spd = 3.9
            elif u < 0.80:
                spd = 3.9 * max(0.0, 1.0 - (u - 0.28) / 0.52)
            else:
                spd = 0.0
            p["vel"][0] = math.sin(rad) * spd
            p["vel"][1] = math.cos(rad) * spd
            p["backpedal"] = 0.0
            p["jockey"] = 0.0
        elif act in ("parry", "disbelief", "breather") or (
            act in ("header", "chest", "trap") and not p["action_pending"]
        ):
            brake = math.exp(-10.0 * dt)
            p["vel"][0] *= brake
            p["vel"][1] *= brake
            want_yaw = math.degrees(math.atan2(look_pos[0] - px, look_pos[1] - pz))
            p["yaw"] = _turn_toward(p["yaw"], want_yaw, 460.0 * dt)
            p["backpedal"] = max(0.0, p["backpedal"] - 5.0 * dt)
            p["jockey"] = max(0.0, p["jockey"] - 5.0 * dt)
        elif act in ("kick", "trap", "chest", "header") and p["action_pending"]:
            dx, dz = tx - px, tz - pz
            dist = math.hypot(dx, dz)
            if dist > 0.08:
                spd = min(max_spd * 0.72, max_spd * min(1.0, dist / 0.25))
                wx, wz = dx / dist * spd, dz / dist * spd
            else:
                wx = wz = 0.0
            blend_k = 1.0 - math.exp(-14.0 * dt)
            p["vel"][0] += (wx - p["vel"][0]) * blend_k
            p["vel"][1] += (wz - p["vel"][1]) * blend_k
            if p["action_subtype"] != "backheel":
                want_yaw = math.degrees(math.atan2(look_pos[0] - px, look_pos[1] - pz))
                p["yaw"] = _turn_toward(p["yaw"], want_yaw, 680.0 * dt)
            p["backpedal"] = max(0.0, p["backpedal"] - 6.0 * dt)
            p["jockey"] = max(0.0, p["jockey"] - 6.0 * dt)
        elif act == "kick" and p["action_t"] < p["action_hit"] + 0.10:
            brake = math.exp(-11.0 * dt)
            p["vel"][0] *= brake
            p["vel"][1] *= brake
            if p["action_subtype"] != "backheel":
                want_yaw = math.degrees(math.atan2(look_pos[0] - px, look_pos[1] - pz))
                p["yaw"] = _turn_toward(p["yaw"], want_yaw, 520.0 * dt)
            p["backpedal"] = max(0.0, p["backpedal"] - 5.0 * dt)
            p["jockey"] = max(0.0, p["jockey"] - 5.0 * dt)
        else:
            dx, dz = tx - px, tz - pz
            dist = math.hypot(dx, dz)
            if dist > 0.12:
                ramp = 0.28 if math.hypot(self.ball_pos[0] - px, self.ball_pos[2] - pz) < 1.35 else 0.40
                spd = min(max_spd, max_spd * min(1.0, dist / ramp))
                wx, wz = dx / dist * spd, dz / dist * spd
            else:
                wx = wz = 0.0
            blend_k = 1.0 - math.exp(-12.5 * dt)
            p["vel"][0] += (wx - p["vel"][0]) * blend_k
            p["vel"][1] += (wz - p["vel"][1]) * blend_k

            cur_spd = math.hypot(p["vel"][0], p["vel"][1])
            lx, lz = look_pos[0] - px, look_pos[1] - pz
            ld = math.hypot(lx, lz) or 1.0
            look_yaw = math.degrees(math.atan2(lx, lz)) if ld > 0.05 else p["yaw"]
            if cur_spd > 0.40 and dist > 0.30:
                vel_dot_look = (p["vel"][0] * lx + p["vel"][1] * lz) / (cur_spd * ld)
                bp_thresh = 0.45 if p["backpedal"] > 0.5 else 0.25
                keep_facing = (self.mode == "shot" and name != self.turn) or (name != self.turn and dist < 5.8)
                # Keep facing the ball when shuffling laterally or retreating, unless sprinting far away
                if vel_dot_look < bp_thresh and (keep_facing or cur_spd < 3.45 or dist < 3.8):
                    want_yaw = look_yaw
                    target_bp = 1.0
                else:
                    want_yaw = math.degrees(math.atan2(p["vel"][0], p["vel"][1]))
                    target_bp = 0.0
            else:
                want_yaw = look_yaw
                target_bp = 0.0

            p["backpedal"] += (target_bp - p["backpedal"]) * (1.0 - math.exp(-8.0 * dt))
            is_dfn = (name != self.turn) or (self.mode == "shot")
            target_jockey = 1.0 if (is_dfn and cur_spd < 0.70 and act is None) else 0.0
            p["jockey"] += (target_jockey - p["jockey"]) * (1.0 - math.exp(-7.0 * dt))
            p["yaw"] = _turn_toward(p["yaw"], want_yaw, 560.0 * dt)

        dyaw = ((p["yaw"] - old_yaw + 180.0) % 360.0 - 180.0) / max(1e-4, dt)
        p["yaw_vel"] += (dyaw - p["yaw_vel"]) * (1.0 - math.exp(-10.0 * dt))

        nx = _clamp(px + p["vel"][0] * dt, -self.PITCH_HX - 1.5, self.PITCH_HX + 1.5)
        nz = _clamp(pz + p["vel"][1] * dt, -self.PITCH_HZ - 0.8, self.PITCH_HZ + 0.8)

        # Keep clear of upright goalposts and net mesh walls cleanly.
        for side in (-1.0, 1.0):
            gx = side * self.PITCH_HX
            for pz_post in (-self.GOAL_HW, self.GOAL_HW):
                ox, oz = nx - gx, nz - pz_post
                d = math.hypot(ox, oz)
                if 1e-5 < d < 0.36:
                    nx = gx + ox / d * 0.36
                    nz = pz_post + oz / d * 0.36
            if side * nx > self.PITCH_HX + 0.05 and side * nx < self.PITCH_HX + self.GOAL_D + 0.35:
                if abs(nz) < self.GOAL_HW - 0.28:
                    if side * nx > self.PITCH_HX + self.GOAL_D - 0.32:
                        nx = gx + side * (self.GOAL_D - 0.32)
                elif abs(nz) < self.GOAL_HW + 0.34:
                    nz = math.copysign(self.GOAL_HW + 0.34, nz)

        p["pos"][0], p["pos"][1] = nx, nz
        spd = math.hypot(p["vel"][0], p["vel"][1])
        if spd > 0.14 and act not in ("dive", "slide"):
            step_dir = -1.0 if p["backpedal"] > 0.5 else 1.0
            p["gait"] = (p["gait"] + step_dir * spd * 3.65 * dt) % (2.0 * math.pi)

    def _step_actions(self, dt):
        bx, by, bz = self.ball_pos
        for name in ("biribel", "bodi"):
            p = self.players[name]
            if p["beckon_t"] > 0.0:
                p["beckon_t"] = max(0.0, p["beckon_t"] - dt)
            act = p["action"]
            if act is None:
                continue
            p["action_t"] += dt

            if p["action_pending"] and act not in ("dive", "slide"):
                px, pz = p["pos"]
                d_b = math.hypot(bx - px, bz - pz)
                receive = act in ("trap", "chest", "header", "parry")
                in_reach = (
                    (act == "trap" and d_b < 0.50 and by < 0.62)
                    or (act == "chest" and d_b < 0.50 and 0.56 <= by <= 1.15)
                    or (act == "header" and d_b < 0.52 and 0.85 <= by <= 1.80)
                    or (act == "parry" and d_b < 0.66 and by < 1.65)
                )
                fire = False
                if receive and in_reach and p["action_t"] >= p["action_hit"] * 0.6:
                    fire = True
                elif p["action_t"] >= p["action_hit"]:
                    vx, _vy, vz = self.ball_vel
                    hold = p["action_meta"].get("hold", 0.0)
                    if receive and (px - bx) * vx + (pz - bz) * vz > 0.0 and hold < 0.26:
                        # Freeze on the reach pose until the ball actually arrives at foot/chest/head.
                        p["action_meta"]["hold"] = hold + dt
                        p["action_t"] = p["action_hit"]
                    else:
                        fire = True
                if fire:
                    p["action_pending"] = False
                    self._execute_action_hit(name, p)

            # Trail dust on slides / knee slides / dive landing
            u = p["action_t"] / max(1e-4, p["action_dur"])
            if act == "slide" and 0.08 < u < 0.48 and self._puff_acc >= 0.09:
                self._puff_acc = 0.0
                self._spawn_puff(p["pos"][0], 0.04, p["pos"][1], count=2, spread=0.9, col_idx=0, tier=1)
            elif act == "celebrate" and p["action_subtype"] == "knee_slide" and 0.28 < u < 0.72 and self._puff_acc >= 0.09:
                self._puff_acc = 0.0
                self._spawn_puff(p["pos"][0], 0.04, p["pos"][1], count=2, spread=0.8, col_idx=1, tier=1)
            elif act == "dive" and 0.44 <= u < 0.50 and self._puff_acc >= 0.06:
                self._puff_acc = 0.0
                self._spawn_puff(p["pos"][0], 0.05, p["pos"][1], count=4, spread=1.5, col_idx=0, tier=2)

            if act == "celebrate" and p["action_subtype"] in ("banter", "fist_pump"):
                p["mouth"] = 0.28 * (0.5 + 0.5 * math.sin(self.t * 13.0))
            else:
                p["mouth"] = 0.0

            if p["action_t"] >= p["action_dur"]:
                p["action"] = None
                p["action_pending"] = False
                p["expr"] = "smile"
                p["mouth"] = 0.0

    def _step_body_collisions(self):
        bx, by, bz = self.ball_pos
        vx, vy, vz = self.ball_vel
        for name in ("biribel", "bodi"):
            p = self.players[name]
            px, pz = p["pos"]
            act = p["action"]

            if act == "dive" and p["action_pending"] and 0.05 <= p["action_t"] <= 0.48:
                dyaw = p["action_meta"].get("dive_yaw", p["yaw"])
                rad = math.radians(dyaw)
                fx, fz = math.sin(rad), math.cos(rad)
                d_seg = self._dist_point_seg_xz(bx, bz, px + 0.10 * fx, pz + 0.10 * fz, px + 1.38 * fx, pz + 1.38 * fz)
                dive_y = p["action_meta"].get("target_y", 0.90)
                if d_seg < self.BALL_R + 0.34 and max(0.0, dive_y - 0.58) <= by <= dive_y + 0.62:
                    p["action_pending"] = False
                    p["touch_grace"] = 0.28
                    atk_dir = 1.0 if px < 0.0 else -1.0
                    self.ball_vel = [
                        atk_dir * self._rng.uniform(3.4, 5.2),
                        self._rng.uniform(1.1, 2.1),
                        _clamp(-pz * 0.9 + self._rng.uniform(-1.4, 1.4), -2.8, 2.8)
                        if abs(pz) > 0.6 else
                        (math.copysign(self._rng.uniform(1.8, 3.0), bz - pz) if abs(bz - pz) > 0.05 else self._rng.choice((-2.2, 2.2))),
                    ]
                    self.ball_spin_y = self._rng.uniform(-2.0, 2.0)
                    self._spawn_puff(bx, by, bz, count=4, spread=1.6, col_idx=2, tier=2)
                    self.turn = name
                    self.mode = "rally"
                    self._reroll_possession()
                    self.cooldown = 0.34
                    bx, by, bz = self.ball_pos
                    vx, vy, vz = self.ball_vel
                continue

            if act == "slide" and p["action_pending"] and 0.04 <= p["action_t"] <= 0.44:
                syaw = p["action_meta"].get("slide_yaw", p["yaw"])
                rad = math.radians(syaw)
                fx, fz = math.sin(rad), math.cos(rad)
                d_seg = self._dist_point_seg_xz(bx, bz, px, pz, px + 0.94 * fx, pz + 0.94 * fz)
                if d_seg < self.BALL_R + 0.28 and by < 0.58:
                    p["action_pending"] = False
                    p["touch_grace"] = 0.28
                    self.ball_vel = [fx * 5.4, 0.85, fz * 5.4]
                    self._spawn_puff(bx, 0.05, bz, count=3, spread=1.4, col_idx=0, tier=1)
                    self.turn = name
                    self._reroll_possession()
                    self.cooldown = 0.32
                    bx, by, bz = self.ball_pos
                    vx, vy, vz = self.ball_vel
                continue

            if act in ("dive", "slide") or p["action_pending"] or p["touch_grace"] > 0.0 or self.mode == "goal":
                continue
            if by > 1.48:
                continue
            body_r = 0.24 if by > 1.12 else (0.29 if by > 0.62 else 0.30)
            hit_r = body_r + self.BALL_R
            dx, dz = bx - px, bz - pz
            dist = math.hypot(dx, dz)
            if dist >= hit_r:
                continue
            nx, nz = (dx / dist, dz / dist) if dist > 1e-5 else (math.sin(math.radians(p["yaw"])), math.cos(math.radians(p["yaw"])))
            rvx, rvz = vx - p["vel"][0], vz - p["vel"][1]
            v_in = rvx * nx + rvz * nz
            rel_spd = math.hypot(rvx, rvz)
            if v_in >= -0.35:
                continue
            if rel_spd <= 2.2 and name == self.turn and self.mode == "rally":
                continue
            bx = px + nx * (hit_r + 0.02)
            bz = pz + nz * (hit_r + 0.02)
            self.ball_pos[0], self.ball_pos[2] = bx, bz
            p["touch_grace"] = 0.24
            if self.mode == "shot" and name != self.turn:
                atk_dir = -1.0 if px < 0.0 else 1.0
                self.ball_vel = [
                    -atk_dir * self._rng.uniform(2.8, 4.3),
                    self._rng.uniform(0.85, 1.75),
                    _clamp((bz - pz) * 2.3 + self._rng.uniform(-0.8, 0.8), -2.4, 2.4),
                ]
                self._start_action(p, "parry", 0.34, hit=0.06, expr="grin", target_y=by, contact_pos=(bx, by, bz))
                p["action_pending"] = False
                self._spawn_puff(bx, by, bz, count=3, spread=1.2, col_idx=2, tier=1)
                self.turn = name
                self.mode = "rally"
                self._reroll_possession()
                self.cooldown = 0.26
            else:
                bounce = 0.42 if rel_spd > 4.5 else 0.28
                vx = vx - (1.0 + bounce) * v_in * nx + p["vel"][0] * 0.25
                vz = vz - (1.0 + bounce) * v_in * nz + p["vel"][1] * 0.25
                vy = max(vy * 0.4, 0.25) if by > 0.45 else max(vy * 0.5, 0.05)
                self.ball_vel = [vx, vy, vz]
                if by >= 1.06:
                    self._start_action(p, "header", 0.34, hit=0.10, expr="surprised", target_y=by, contact_pos=(bx, by, bz))
                elif by >= 0.62:
                    self._start_action(p, "chest", 0.32, hit=0.09, expr="smile", target_y=by, contact_pos=(bx, by, bz))
                else:
                    foot = self._pick_foot(p, bx, bz)
                    self._start_action(p, "trap", 0.28, hit=0.08, foot=foot, expr="smile", target_y=by, contact_pos=(bx, by, bz))
                p["action_pending"] = False
                # Ball already touched: skip the windup so the contact keyframe shows now, not 0.1 s late.
                p["action_t"] = p["action_dur"] * 0.38
                self._spawn_puff(bx, max(0.04, by * 0.5), bz, count=2, spread=0.8, col_idx=1, tier=0)
                self.turn = name
                self.dribble_left = self._rng.randint(0, 1)
                self.cooldown = 0.16
            vx, vy, vz = self.ball_vel

    def step(self, dt):
        dt = max(0.0, min(float(dt or 0.0), 0.05))
        if dt <= 0.0:
            return
        self.t += dt
        self._puff_acc += dt
        for p in self.players.values():
            if p["touch_grace"] > 0.0:
                p["touch_grace"] = max(0.0, p["touch_grace"] - dt)
        if self.cooldown > 0.0:
            self.cooldown = max(0.0, self.cooldown - dt)
        if self.slide_cd > 0.0:
            self.slide_cd = max(0.0, self.slide_cd - dt)
        if self.feint_cd > 0.0:
            self.feint_cd = max(0.0, self.feint_cd - dt)
        if self.breather_cd > 0.0:
            self.breather_cd = max(0.0, self.breather_cd - dt)
        if self.clang_t > 0.0:
            self.clang_t = max(0.0, self.clang_t - dt)

        prev_acts = {n: self.players[n]["action"] for n in ("biribel", "bodi")}

        self._step_actions(dt)
        self._step_ball(dt)
        self._step_body_collisions()
        self._step_puffs(dt)

        bx, by, bz = self.ball_pos
        vx, vy, vz = self.ball_vel
        ball_spd = math.hypot(vx, vz)

        att_name = self.turn
        dfn_name = "bodi" if att_name == "biribel" else "biribel"
        att = self.players[att_name]
        dfn = self.players[dfn_name]
        atk_dir = 1.0 if att_name == "biribel" else -1.0
        goal_x = atk_dir * self.PITCH_HX

        if self.mode == "goal":
            self.goal_t += dt
            sc_name = self.scorer or "biribel"
            fe_name = "bodi" if sc_name == "biribel" else "biribel"
            sc_side = 1.0 if sc_name == "biribel" else -1.0
            sc = self.players[sc_name]
            fe = self.players[fe_name]

            if sc["action"] == "celebrate":
                sub = sc["action_subtype"]
                if sub == "knee_slide":
                    if "slide_yaw" not in sc["action_meta"]:
                        sc["action_meta"]["slide_yaw"] = math.degrees(
                            math.atan2(sc_side * 1.4, -sc["pos"][1] * 0.5)
                        )
                    self._steer_player(sc_name, sc_side * 2.5, 0.0, 3.6, (0.0, 0.0), dt)
                elif sub == "aeroplane":
                    ang = self.goal_t * 2.4
                    self._steer_player(
                        sc_name,
                        sc_side * 2.1 + math.cos(ang) * 1.4,
                        math.sin(ang) * 1.8,
                        3.3,
                        (0.0, 0.0),
                        dt,
                    )
                else:
                    self._steer_player(sc_name, sc_side * 2.0, 0.0, 1.3, fe["pos"], dt)
            else:
                self._steer_player(sc_name, sc_side * 1.6, 0.0, 1.6, (bx, bz), dt)

            if self.goal_t < 0.65:
                self._steer_player(fe_name, fe["pos"][0], fe["pos"][1], 0.0, (bx, bz), dt)
            else:
                if sc_side * fe["pos"][0] > self.PITCH_HX - 0.4 and abs(fe["pos"][1]) > self.GOAL_HW - 0.5:
                    tx_f, tz_f = sc_side * (self.PITCH_HX - 0.9), _clamp(bz, -1.2, 1.2)
                else:
                    tx_f = sc_side * min(abs(bx) + 0.34, self.PITCH_HX + self.GOAL_D - 0.36)
                    tz_f = _clamp(bz, -1.5, 1.5)
                self._steer_player(fe_name, tx_f, tz_f, 3.1, (0.0, 0.0), dt)
                # Rally resumes only once the restart kick has carried the ball out of the
                # net; switching at kick start re-scored the still-netted ball every frame.
                if self.goal_t >= 1.45 and abs(bx) < self.PITCH_HX - 0.3:
                    self.turn = sc_name
                    self.mode = "rally"
                    self._reroll_possession()
                elif (
                    self.goal_t >= 1.45
                    and fe["action"] is None
                    and self.cooldown <= 0.0
                    and math.hypot(fe["pos"][0] - bx, fe["pos"][1] - bz) < 0.90
                ):
                    self._kick_ball(fe, 0.0, 0.6 if bz < 0 else -0.6, 6.8, 2.0, "pass")
                elif self.goal_t > 4.2:
                    self.ball_pos = [0.0, self.BALL_R, 0.0]
                    self.ball_vel = [0.0, 0.0, 0.0]
                    self.ball_spin_y = 0.0
                    self.turn = fe_name
                    self.mode = "rally"
                    self._reroll_possession()

        elif self.mode == "shot":
            self.shot_t += dt
            if (goal_x - bx) * vx > 0.0:
                pred_z, pred_y, t_cross = self._predict_shot_plane(goal_x, atk_dir)
            else:
                pred_z = _clamp(bz, -1.5, 1.5)
                pred_y = _clamp(by, self.BALL_R, self.GOAL_H)
                t_cross = 1.5

            tgt_z = _clamp(pred_z, -1.65, 1.65)
            self._steer_player(dfn_name, goal_x - atk_dir * 1.05, _clamp(tgt_z, -1.58, 1.58), 3.90, (bx, bz), dt)
            follow_x = _clamp(att["pos"][0] + atk_dir * 0.7, -self.PITCH_HX + 2.0, self.PITCH_HX - 2.0)
            self._steer_player(att_name, follow_x, att["pos"][1], 1.8, (bx, bz), dt)

            d_dfn = math.hypot(bx - dfn["pos"][0], bz - dfn["pos"][1])
            dist_to_line = abs(goal_x - bx)
            lat_gap = abs(pred_z - dfn["pos"][1])

            # Superman diving save for fast corner-bound shots!
            if (
                dfn["action"] is None
                and self.shot_t > 0.04
                and dist_to_line < 5.6
                and t_cross <= 0.62
                and ball_spd > 4.4
                and abs(pred_z) <= self.GOAL_HW + 0.25
                and 0.42 <= lat_gap <= 2.55
                and (goal_x - bx) * vx > 0.0
            ):
                dive_tx = goal_x - atk_dir * 1.05
                dive_tz = _clamp(pred_z, -self.GOAL_HW + 0.38, self.GOAL_HW - 0.38)
                dyaw = math.degrees(math.atan2(dive_tx - dfn["pos"][0], dive_tz - dfn["pos"][1]))
                self._start_action(dfn, "dive", 0.80, hit=0.22, expr="stern", dive_yaw=dyaw, target_y=pred_y)
                self._spawn_puff(dfn["pos"][0], 0.04, dfn["pos"][1], count=3, spread=1.2, col_idx=1, tier=1)
            elif (
                dfn["action"] is None
                and self.shot_t > 0.04
                and (goal_x - bx) * vx > 0.0
                and lat_gap < 0.72
                and 0.04 <= t_cross <= 0.18
                and pred_y < 1.62
            ):
                dur = max(0.28, t_cross / 0.25)
                self._start_action(dfn, "parry", dur, hit=t_cross, expr="grin", target_y=pred_y)
            elif dfn["action"] is None and self.shot_t > 0.05 and d_dfn < 0.76 and by < 1.62:
                self._start_action(dfn, "parry", 0.36, hit=0.09, expr="grin", target_y=by, contact_pos=(bx, by, bz))
                dfn["action_t"] = 0.09
                dfn["action_pending"] = False
                self._execute_action_hit(dfn_name, dfn)
            elif (
                (self.shot_t > 0.10 and atk_dir * vx < -0.45)
                or (self.shot_t > 0.45 and ball_spd < 1.8)
                or (abs(bx) > self.PITCH_HX + 0.12 and abs(bz) >= self.GOAL_HW)
            ):
                if abs(bx) > self.PITCH_HX and abs(bz) < self.GOAL_HW + 1.35 and att["action"] is None:
                    self._start_action(att, "disbelief", 0.68, expr="worried")
                elif self.breather_cd <= 0.0 and att["action"] is None and self._rng.random() < 0.28:
                    self._start_action(att, "breather", 0.95, expr="smile")
                    self.breather_cd = self._rng.uniform(8.0, 15.0)
                self.mode = "rally"
                d_a = math.hypot(bx - att["pos"][0], bz - att["pos"][1])
                d_d = math.hypot(bx - dfn["pos"][0], bz - dfn["pos"][1])
                self.turn = att_name if d_a <= d_d else dfn_name
                self._reroll_possession()

        else:
            # Rally: aerial control, dribbles, feints, sliding tackles, passes, shots
            samples = self._ball_samples(horizon=0.72, step=0.045)
            if ball_spd < 0.35:
                self.stall_t += dt
            else:
                self.stall_t = 0.0

            if self.rally_passes < self.target_passes:
                if self._press_mode:
                    sup_x = _clamp(bx + atk_dir * 3.15, -5.6, 5.6)
                    sup_z = _clamp(bz * 0.72 + (0.95 if bz < 0.0 else -0.95), -3.1, 3.1)
                else:
                    sup_x = _clamp(bx + atk_dir * 3.85, -5.5, 5.5)
                    sup_z = -2.85 if bz >= 0.0 else 2.85
                self._steer_player(dfn_name, sup_x, sup_z, 3.25, (bx, bz), dt)
                # Off-ball player occasionally calls for the pass
                if (
                    not self._press_mode
                    and dfn["action"] is None
                    and dfn["beckon_t"] <= 0.0
                    and math.hypot(dfn["pos"][0] - bx, dfn["pos"][1] - bz) > 3.2
                    and self._rng.random() < 0.025
                ):
                    dfn["beckon_t"] = 0.72
            else:
                def_x = _clamp(bx + atk_dir * 3.2, -self.PITCH_HX + 1.15, self.PITCH_HX - 1.15)
                if atk_dir > 0.0 and bx > goal_x - 3.6:
                    def_x = goal_x - 1.15
                elif atk_dir < 0.0 and bx < goal_x + 3.6:
                    def_x = goal_x + 1.15
                self._steer_player(
                    dfn_name,
                    def_x,
                    _clamp(bz * 0.45, -1.35, 1.35),
                    3.35,
                    (bx, bz),
                    dt,
                )

            dist_ball = math.hypot(bx - att["pos"][0], bz - att["pos"][1])
            dist_dfn_ball = math.hypot(bx - dfn["pos"][0], bz - dfn["pos"][1])

            # Defender sliding tackle on a loose ball ahead of the carrier
            drad = math.radians(dfn["yaw"])
            dbx, dbz = bx - dfn["pos"][0], bz - dfn["pos"][1]
            dbd = math.hypot(dbx, dbz) or 1.0
            dfn_ball_dot = (dbx * math.sin(drad) + dbz * math.cos(drad)) / dbd
            if (
                dfn["action"] is None
                and att["action"] in (None, "dribble")
                and self.slide_cd <= 0.0
                and self.cooldown <= 0.1
                and 1.00 < dist_dfn_ball < 1.85
                and dist_ball > 1.10
                and dfn_ball_dot > 0.45
                and by < 0.40
                and abs(bx) < self.PITCH_HX - 1.2
                and self._rng.random() < 0.06
            ):
                syaw = math.degrees(math.atan2(bx - dfn["pos"][0], bz - dfn["pos"][1]))
                self._start_action(dfn, "slide", 0.66, hit=0.18, expr="stern", slide_yaw=syaw)
                self.slide_cd = self._rng.uniform(5.5, 9.5)

            # Decide carrier's target kick when no action is currently active
            out_edge = (
                abs(bz) > self.PITCH_HZ - 0.75
                or (abs(bx) > self.PITCH_HX - 0.70 and (abs(bz) >= self.GOAL_HW + 0.35 or atk_dir * bx < 0.0))
            )
            ready_shot = (
                (atk_dir * bx >= 3.0 and abs(bz) < 3.2)
                or (self.rally_passes >= self.target_passes and atk_dir * bx >= 0.8 and abs(bz) < 3.9)
                or (self.rally_passes >= 1 and atk_dir * bx >= 2.0 and abs(bz) < 3.0 and self._rng.random() < 0.35)
            )
            if out_edge:
                kick_kind = "pass"
                kx = _clamp(dfn["pos"][0] * 0.5, -3.0, 3.0)
                kz = _clamp(dfn["pos"][1] * 0.5, -2.0, 2.0)
                kspeed, kloft, kcurl = 6.2, 1.1, 0.0
            elif ready_shot:
                kick_kind = "shot"
                kx, kz, kspeed, kloft, kcurl = self._pick_shot_target(goal_x, atk_dir, bx, bz, dfn_z=dfn["pos"][1])
            elif self.dribble_left > 0 and atk_dir * bx < 4.5:
                kick_kind = "dribble"
                open_z_dir = -1.0 if dfn["pos"][1] > bz + 0.3 else (1.0 if dfn["pos"][1] < bz - 0.3 else self._dribble_dir)
                lat_push = 1.45 if math.hypot(att["pos"][0] - dfn["pos"][0], att["pos"][1] - dfn["pos"][1]) < 2.4 else 0.95
                kx = _clamp(bx + atk_dir * 2.70, -5.6, 5.6)
                kz = _clamp(bz + open_z_dir * lat_push, -self.PITCH_HZ + 0.9, self.PITCH_HZ - 0.9)
                att_spd = math.hypot(att["vel"][0], att["vel"][1])
                kspeed = _clamp(max(3.6, att_spd + 0.95), 3.6, 4.45)
                kloft, kcurl = 0.12, 0.0
            else:
                lead_x = _clamp(dfn["pos"][0] + dfn["vel"][0] * 0.35, -5.2, 5.2)
                lead_z = _clamp(dfn["pos"][1] + dfn["vel"][1] * 0.35, -3.6, 3.6)
                kx, kz = lead_x, lead_z
                dist_p = math.hypot(kx - bx, kz - bz)
                rad = math.radians(att["yaw"])
                fwd_dot = ((kx - bx) * math.sin(rad) + (kz - bz) * math.cos(rad)) / (dist_p or 1.0)
                if fwd_dot < -0.20 and dist_p < 5.0 and self._rng.random() < 0.25:
                    kick_kind = "backheel"
                    kspeed, kloft, kcurl = _clamp(dist_p * 1.1 + 2.2, 5.2, 7.2), 0.4, 0.0
                elif dist_p > 2.5 and self._rng.random() < 0.42:
                    kick_kind = "lob"
                    kspeed = _clamp(dist_p * 0.90 + 1.8, 4.6, 7.0)
                    kloft, kcurl = self._rng.uniform(5.3, 6.6), 0.6
                else:
                    kick_kind = "pass"
                    kspeed = _clamp(dist_p * 1.15 + self._rng.uniform(2.1, 3.1), 5.4, 8.8)
                    kloft = self._rng.uniform(0.4, 1.1)
                    kcurl = self._rng.uniform(-0.8, 0.8)

            # Predictive first-touch / aerial reactions timed to ball arrival
            if att["action"] is None and self.cooldown <= 0.0:
                arr = self._predict_arrival(att_name, samples, max_t=0.24)
                if arr is not None:
                    t_hit, ax, ay, az, aspd, avy = arr
                    if 0.98 <= ay <= 1.65 and avy < 2.5:
                        is_shot = atk_dir * ax >= -0.4 and abs(az) < 3.6
                        if is_shot:
                            hx, hz, hspd, hloft, _ = self._pick_shot_target(goal_x, atk_dir, ax, az, dfn_z=dfn["pos"][1])
                            hspd, hloft = min(hspd, 10.2), min(hloft, 1.4)
                        else:
                            hx = _clamp(dfn["pos"][0] + dfn["vel"][0] * 0.25, -4.5, 4.5)
                            hz = _clamp(dfn["pos"][1] + dfn["vel"][1] * 0.25, -3.2, 3.2)
                            hspd, hloft = 6.2, 1.6
                        hit_t = _clamp(t_hit, 0.08, 0.22)
                        self._start_action(
                            att,
                            "header",
                            max(0.32, hit_t / 0.42),
                            hit=hit_t,
                            expr="stern",
                            target=(hx, hz, hspd, hloft),
                            is_shot=is_shot,
                            target_y=ay,
                        )
                        self.cooldown = 0.36
                    elif 0.62 <= ay < 0.98:
                        hit_t = _clamp(t_hit, 0.07, 0.20)
                        self._start_action(
                            att, "chest", max(0.28, hit_t / 0.38),
                            hit=hit_t, expr="smile", target_y=ay,
                        )
                        self.cooldown = 0.28
                    elif ay < 0.62 and aspd >= 2.8:
                        if kick_kind == "shot" and dist_ball < 1.35 and ay < 0.62:
                            self._kick_ball(att, kx, kz, kspeed, kloft, "shot", curl=kcurl, hit_override=t_hit)
                        elif (
                            kick_kind in ("pass", "lob", "backheel")
                            and self.dribble_left == 0
                            and dist_ball < 1.25
                            and ay < 0.52
                            and self._rng.random() < 0.35
                        ):
                            self._kick_ball(att, kx, kz, kspeed, kloft, kick_kind, curl=kcurl, hit_override=t_hit)
                        else:
                            foot = self._pick_foot(att, ax, az)
                            hit_t = _clamp(t_hit, 0.06, 0.18)
                            self._start_action(
                                att, "trap", max(0.24, hit_t / 0.38),
                                hit=hit_t, foot=foot, expr="smile", target_y=ay,
                            )
                            self.cooldown = 0.22
                elif dist_ball < 1.05 and ball_spd > 1.8:
                    if 0.98 <= by <= 1.65 and vy < 2.4:
                        is_shot = atk_dir * bx >= -0.4 and abs(bz) < 3.6
                        if is_shot:
                            hx, hz, hspd, hloft, _ = self._pick_shot_target(goal_x, atk_dir, bx, bz, dfn_z=dfn["pos"][1])
                            hspd, hloft = min(hspd, 10.2), min(hloft, 1.4)
                        else:
                            hx = _clamp(dfn["pos"][0] + dfn["vel"][0] * 0.25, -4.5, 4.5)
                            hz = _clamp(dfn["pos"][1] + dfn["vel"][1] * 0.25, -3.2, 3.2)
                            hspd, hloft = 6.2, 1.6
                        self._start_action(
                            att, "header", 0.38, hit=0.14, expr="stern",
                            target=(hx, hz, hspd, hloft), is_shot=is_shot, target_y=by,
                        )
                        self.cooldown = 0.36
                    elif 0.62 <= by < 0.98:
                        self._start_action(att, "chest", 0.34, hit=0.12, expr="smile", target_y=by)
                        self.cooldown = 0.28
                    elif by < 0.62 and ball_spd >= 3.2:
                        foot = self._pick_foot(att, bx, bz)
                        self._start_action(att, "trap", 0.28, hit=0.10, foot=foot, expr="smile", target_y=by)
                        self.cooldown = 0.22

            dx_k, dz_k = kx - bx, kz - bz
            dn = math.hypot(dx_k, dz_k) or 1.0
            if att["action"] is not None and att["action_pending"]:
                rem = max(0.02, att["action_hit"] - att["action_t"])
                if att["action"] == "kick" and att["action_subtype"] == "backheel":
                    app_x = _clamp(bx + vx * rem * 0.60 + dx_k / dn * 0.30, -self.PITCH_HX - 1.4, self.PITCH_HX + 1.4)
                    app_z = _clamp(bz + vz * rem * 0.60 + dz_k / dn * 0.30, -self.PITCH_HZ - 0.7, self.PITCH_HZ + 0.7)
                    look_p = (bx - dx_k, bz - dz_k)
                else:
                    fx_k, fz_k = dx_k / dn, dz_k / dn
                    rx_k, rz_k = fz_k, -fx_k
                    side_off = 0.09 if att["action_foot"] == "r" else -0.09
                    off = 0.42 if att["action_subtype"] == "shot" else (0.38 if att["action"] == "kick" else (0.26 if att["action"] == "dribble" else 0.12))
                    app_x = _clamp(bx + vx * rem * 0.70 - fx_k * off - rx_k * side_off, -self.PITCH_HX - 1.4, self.PITCH_HX + 1.4)
                    app_z = _clamp(bz + vz * rem * 0.70 - fz_k * off - rz_k * side_off, -self.PITCH_HZ - 0.7, self.PITCH_HZ + 0.7)
                    look_p = (bx + vx * 0.06, bz + vz * 0.06)
            elif dist_ball > 0.78 and ball_spd > 1.2:
                ix, iz, _ = self._intercept_target(att["pos"][0], att["pos"][1], 3.75, samples)
                app_x = _clamp(ix - dx_k / dn * 0.18, -self.PITCH_HX - 1.4, self.PITCH_HX + 1.4)
                app_z = _clamp(iz - dz_k / dn * 0.18, -self.PITCH_HZ - 0.7, self.PITCH_HZ + 0.7)
                look_p = (bx, bz)
            elif kick_kind == "dribble":
                # Drive smoothly through the ball so the carrier never stops behind it between touches
                app_x = _clamp(bx + dx_k / dn * 0.45 + vx * 0.06, -self.PITCH_HX - 1.4, self.PITCH_HX + 1.4)
                app_z = _clamp(bz + dz_k / dn * 0.45 + vz * 0.06, -self.PITCH_HZ - 0.7, self.PITCH_HZ + 0.7)
                look_p = (bx, bz) if dist_ball > 0.30 else (kx, kz)
            else:
                offset = 0.24 if kick_kind == "dribble" else 0.38
                app_x = _clamp(bx - dx_k / dn * offset + vx * 0.08, -self.PITCH_HX - 1.4, self.PITCH_HX + 1.4)
                app_z = _clamp(bz - dz_k / dn * offset + vz * 0.08, -self.PITCH_HZ - 0.7, self.PITCH_HZ + 0.7)
                look_p = (bx, bz) if dist_ball > 0.25 else (kx, kz)
            self._steer_player(att_name, app_x, app_z, 3.75 if dist_ball > 1.6 else 3.35, look_p, dt)

            # Occasional step-over feint while carrying into defender
            if (
                att["action"] is None
                and self.feint_cd <= 0.0
                and dist_ball < 0.95
                and math.hypot(att["pos"][0] - dfn["pos"][0], att["pos"][1] - dfn["pos"][1]) < 2.6
                and self.dribble_left > 0
                and ball_spd < 4.2
                and self._rng.random() < 0.14
            ):
                foot = self._rng.choice(("l", "r"))
                self._start_action(att, "feint", 0.38, foot=foot, expr="grin")
                self.feint_cd = self._rng.uniform(3.2, 6.2)

            arad = math.radians(att["yaw"])
            adx, adz = bx - att["pos"][0], bz - att["pos"][1]
            ad = math.hypot(adx, adz) or 1.0
            att_ball_dot = (adx * math.sin(arad) + adz * math.cos(arad)) / ad
            kick_rad = 0.50 if kick_kind == "dribble" else 0.56
            aligned = (att_ball_dot < -0.15) if kick_kind == "backheel" else (att_ball_dot > 0.30 or dist_ball < 0.22)
            if (
                att["action"] is None
                and self.cooldown <= 0.0
                and dist_ball < kick_rad
                and by < 0.58
                and (ball_spd < 5.4 or self.stall_t > 0.8)
                and (aligned or self.stall_t > 0.6)
            ):
                self._kick_ball(att, kx, kz, kspeed, kloft, kick_kind, curl=kcurl)
            elif self.stall_t > 2.2:
                d_a = math.hypot(bx - att["pos"][0], bz - att["pos"][1])
                d_d = math.hypot(bx - dfn["pos"][0], bz - dfn["pos"][1])
                if d_d + 0.5 < d_a:
                    self.turn = dfn_name
                self.stall_t = 0.0

        # Separate overlapping torsos unless mid-slide/dive contact.
        pa, pb = self.players["biribel"]["pos"], self.players["bodi"]["pos"]
        dx, dz = pb[0] - pa[0], pb[1] - pa[1]
        sep = math.hypot(dx, dz)
        if 1e-5 < sep < 0.78:
            air_a = self.players["biribel"]["action"] in ("dive", "slide")
            air_b = self.players["bodi"]["action"] in ("dive", "slide")
            scale = 0.20 if (air_a or air_b) else 0.58
            push = (0.78 - sep) * scale
            nx, nz = dx / sep, dz / sep
            pa[0] -= nx * push
            pa[1] -= nz * push
            pb[0] += nx * push
            pb[1] += nz * push

        # Broadcast follow framing ball + both players; dolly out as they spread apart.
        fx = bx * 0.5 + (pa[0] + pb[0]) * 0.25
        fz = bz * 0.5 + (pa[1] + pb[1]) * 0.25
        spread = max(math.hypot(pa[0] - bx, pa[1] - bz), math.hypot(pb[0] - bx, pb[1] - bz))
        want_d = _clamp(5.0 + spread * 0.6, 6.2, 9.4)
        want_tgt = _clamp(fx, -self.PITCH_HX + 1.6, self.PITCH_HX - 1.6)
        cam_k = 1.0 - math.exp(-2.6 * dt)
        self.cam_x += (want_tgt * 0.85 - self.cam_x) * cam_k
        self.tgt_x += (want_tgt - self.tgt_x) * cam_k
        self.tgt_z += (_clamp(fz, -2.6, 2.6) - self.tgt_z) * cam_k
        self.cam_d += (want_d - self.cam_d) * (1.0 - math.exp(-1.6 * dt))
        want_fov = 47.5 if self.mode == "goal" and self.goal_t < 2.2 else 50.0
        self.cam_fov += (want_fov - self.cam_fov) * (1.0 - math.exp(-3.0 * dt))

        from engine3d import blend

        for pname in ("biribel", "bodi"):
            pl = self.players[pname]
            cur_act = pl["action"]
            if cur_act != prev_acts[pname]:
                pl["trans_pose"] = dict(pl["pose"]) if pl["pose"] is not None else self._compute_pose(pname)
                if cur_act is None:
                    dur = 0.24 if prev_acts[pname] in ("dive", "slide") else 0.14
                elif cur_act in ("dive", "slide"):
                    dur = 0.08
                else:
                    dur = 0.06
                pl["trans_dur"] = dur
                pl["trans_t"] = dur
            if pl["trans_t"] > 0.0:
                pl["trans_t"] = max(0.0, pl["trans_t"] - dt)

            raw = self._compute_pose(pname)
            if pl["pose"] is None:
                pl["pose"] = dict(raw)
            elif pl["trans_t"] > 0.0 and pl["trans_pose"] is not None:
                q = _smooth(1.0 - pl["trans_t"] / max(1e-4, pl["trans_dur"]))
                pl["pose"] = blend(pl["trans_pose"], raw, q)
            elif cur_act is None:
                pl["pose"] = blend(pl["pose"], raw, 1.0 - math.exp(-18.0 * dt))
            else:
                pl["pose"] = dict(raw)

    def _jockey_pose(self, p, seed):
        from engine3d import POSES

        b = math.sin(self.t * 7.2 + seed)
        return dict(
            POSES["stand"],
            spine=8.0 + 1.0 * abs(b),
            spine_r=4.0 * b,
            lhip_p=10.0 + 2.5 * b,
            lkn=18.0 + 3.5 * b,
            lhip_r=10.0,
            lank=10.0,
            rhip_p=10.0 - 2.5 * b,
            rkn=18.0 - 3.5 * b,
            rhip_r=10.0,
            rank=10.0,
            lsh_p=6.0,
            lsh_r=16.0 + 3.0 * b,
            lel=22.0,
            rsh_p=6.0,
            rsh_r=16.0 - 3.0 * b,
            rel=22.0,
        )

    def _base_locomotion_pose(self, p, seed):
        from engine3d import POSES, blend, pose_run

        spd = math.hypot(p["vel"][0], p["vel"][1])
        sway = math.sin(self.t * 2.6 + seed)
        stand = dict(
            POSES["stand"],
            spine=6.0 + 1.0 * abs(sway),
            lhip_p=6.0,
            lkn=12.0,
            rhip_p=6.0,
            rkn=12.0,
            lsh_r=12.0,
            rsh_r=12.0,
            lel=20.0,
            rel=20.0,
        )
        idle = blend(stand, self._jockey_pose(p, seed), p["jockey"]) if p["jockey"] > 0.02 else stand
        run_w = _smooth((spd - 0.14) / 1.85)
        if run_w <= 0.01:
            return idle
        lean = -3.0 if p["backpedal"] > 0.5 else (6.0 if spd < 2.2 else 13.0)
        run = pose_run(p["gait"], lean=lean)
        if p["backpedal"] > 0.05:
            jock = self._jockey_pose(p, seed)
            run = blend(run, jock, 0.35 * p["backpedal"])
        # Turn banking
        bank = _clamp(-p["yaw_vel"] * 0.020, -8.0, 8.0)
        run["spine_r"] = run.get("spine_r", 0.0) + bank
        return run if run_w >= 0.99 else blend(idle, run, run_w)

    def _action_pose(self, p, base, seed):
        from engine3d import POSES, blend

        act = p["action"]
        u = _clamp(p["action_t"] / max(1e-4, p["action_dur"]), 0.0, 1.0)
        foot = p["action_foot"]
        sub = p["action_subtype"]

        def _seq(keyframes):
            for (u0, p0), (u1, p1) in zip(keyframes, keyframes[1:]):
                if u <= u1:
                    q = _smooth((u - u0) / max(1e-4, u1 - u0))
                    return blend(p0, p1, q)
            return keyframes[-1][1]

        if act == "kick":
            by_off = _clamp(p["action_meta"].get("target_y", self.BALL_R) - self.BALL_R, 0.0, 0.70)
            hip_lift, kn_bend = by_off * 28.0, by_off * 10.0
            if sub == "shot":
                wind = dict(
                    POSES["stand"],
                    spine=10, spine_r=-12, twist=22,
                    lhip_p=18, lkn=24, lhip_r=8,
                    rhip_p=-42, rhip_r=10, rkn=82, rank=22,
                    lsh_p=42, lsh_r=38, lel=28, rsh_p=-26, rsh_r=28, rel=26,
                )
                hit = dict(
                    POSES["stand"],
                    spine=18, spine_r=-12, twist=-6, lift=0.01,
                    lhip_p=16, lkn=24,
                    rhip_p=42 + hip_lift, rhip_r=8, rkn=14 + kn_bend, rank=26,
                    lsh_p=34, lsh_r=44, lel=26, rsh_p=12, rsh_r=30, rel=32,
                )
                follow = dict(
                    POSES["stand"],
                    spine=8, spine_r=-10, twist=-22, lift=0.05,
                    lhip_p=10, lkn=14,
                    rhip_p=66 + hip_lift * 0.5, rhip_r=10, rkn=10, rank=24,
                    lsh_p=18, lsh_r=42, lel=30, rsh_p=38, rsh_r=30, rel=36,
                )
            elif sub == "lob":
                wind = dict(
                    POSES["stand"],
                    spine=4, spine_r=-8, twist=14,
                    lhip_p=16, lkn=22, rhip_p=-32, rkn=64, rank=16,
                    lsh_p=32, lsh_r=32, lel=32, rsh_p=-18, rsh_r=24, rel=26,
                )
                hit = dict(
                    POSES["stand"],
                    spine=-6, spine_r=-8, twist=-6,
                    lhip_p=16, lkn=20, rhip_p=40 + hip_lift, rkn=18 + kn_bend, rank=30,
                    lsh_p=26, lsh_r=38, lel=30, rsh_p=18, rsh_r=28, rel=34,
                )
                follow = dict(
                    POSES["stand"],
                    spine=-10, spine_r=-6, twist=-14,
                    lhip_p=12, lkn=14, rhip_p=60 + hip_lift * 0.5, rkn=14, rank=26,
                    lsh_p=20, lsh_r=34, lel=30, rsh_p=30, rsh_r=28, rel=36,
                )
            elif sub == "backheel":
                wind = dict(
                    POSES["stand"],
                    spine=14, spine_r=-4, twist=-6,
                    lhip_p=18, lkn=20, rhip_p=24, rkn=26,
                    lsh_p=26, lsh_r=28, lel=38, rsh_p=26, rsh_r=28, rel=38,
                )
                hit = dict(
                    POSES["stand"],
                    spine=20, spine_r=-6, twist=14,
                    lhip_p=20, lkn=24, rhip_p=-36, rkn=36, rank=10,
                    lsh_p=36, lsh_r=32, lel=34, rsh_p=18, rsh_r=26, rel=36,
                )
                follow = dict(
                    POSES["stand"],
                    spine=16, spine_r=-4, twist=18,
                    lhip_p=18, lkn=20, rhip_p=-46, rkn=26, rank=12,
                    lsh_p=30, lsh_r=28, lel=36, rsh_p=12, rsh_r=22, rel=34,
                )
            else:  # side-foot pass
                wind = dict(
                    POSES["stand"],
                    spine=8, spine_r=-6, twist=12,
                    lhip_p=14, lkn=22, lhip_r=6,
                    rhip_p=-28, rhip_r=16, rkn=56, rank=16,
                    lsh_p=24, lsh_r=32, lel=30, rsh_p=-12, rsh_r=24, rel=24,
                )
                hit = dict(
                    POSES["stand"],
                    spine=12, spine_r=-6, twist=-4,
                    lhip_p=14, lkn=22,
                    rhip_p=36 + hip_lift, rhip_r=20, rkn=14 + kn_bend, rank=18,
                    lsh_p=20, lsh_r=36, lel=30, rsh_p=14, rsh_r=28, rel=30,
                )
                follow = dict(
                    POSES["stand"],
                    spine=10, spine_r=-4, twist=-14,
                    lhip_p=12, lkn=18,
                    rhip_p=54 + hip_lift * 0.5, rhip_r=18, rkn=12, rank=18,
                    lsh_p=18, lsh_r=34, lel=28, rsh_p=26, rsh_r=28, rel=34,
                )
            if foot == "l":
                wind = _mirror_lr(wind)
                hit = _mirror_lr(hit)
                follow = _mirror_lr(follow)
            return _seq(((0.0, base), (0.22, wind), (0.42, hit), (0.66, follow), (1.0, base)))

        if act == "dribble":
            poke = dict(base)
            k_hip = "rhip_p" if foot == "r" else "lhip_p"
            k_kn = "rkn" if foot == "r" else "lkn"
            k_ank = "rank" if foot == "r" else "lank"
            poke[k_hip] = max(base.get(k_hip, 0.0) + 14.0, 22.0)
            poke[k_kn] = max(10.0, base.get(k_kn, 0.0) - 10.0)
            poke[k_ank] = 16.0
            poke["spine"] = base.get("spine", 8.0) + 4.0
            w = math.sin(u * math.pi)
            return blend(base, poke, w)

        if act == "feint":
            step1 = dict(
                base,
                spine=18, spine_r=-14, twist=12,
                rhip_p=42, rhip_r=28, rkn=36,
                lsh_r=38, rsh_r=38,
            )
            step2 = dict(base, spine=14, spine_r=12, twist=-10, lsh_r=32, rsh_r=32)
            if foot == "l":
                step1, step2 = _mirror_lr(step1), _mirror_lr(step2)
            return _seq(((0.0, base), (0.38, step1), (0.72, step2), (1.0, base)))

        if act == "trap":
            by_off = _clamp(p["action_meta"].get("target_y", 0.22) - 0.18, 0.0, 0.55)
            lift_p = dict(
                POSES["stand"],
                spine=8, spine_r=-6,
                lhip_p=16, lkn=22,
                rhip_p=28 + by_off * 38.0, rkn=max(12.0, 32 - by_off * 12.0), rhip_r=12, rank=10,
                lsh_p=24, lsh_r=38, lel=34, rsh_p=24, rsh_r=38, rel=34,
            )
            drop_p = dict(
                POSES["stand"],
                spine=12,
                lhip_p=14, lkn=20, rhip_p=18, rkn=20,
                lsh_p=22, lsh_r=28, lel=36, rsh_p=22, rsh_r=28, rel=36,
            )
            if foot == "l":
                lift_p, drop_p = _mirror_lr(lift_p), _mirror_lr(drop_p)
            return _seq(((0.0, base), (0.38, lift_p), (0.72, drop_p), (1.0, base)))

        if act == "chest":
            by_off = _clamp(p["action_meta"].get("target_y", 0.82) - 0.82, -0.20, 0.20)
            arch = dict(
                POSES["stand"],
                spine=-16 - by_off * 22.0, head_p=14,
                lhip_p=16, lkn=26, rhip_p=16, rkn=26,
                lsh_p=12, lsh_r=52, lel=36, rsh_p=12, rsh_r=52, rel=36,
            )
            cushion = dict(
                POSES["stand"],
                spine=12, head_p=20,
                lhip_p=22, lkn=32, rhip_p=22, rkn=32,
                lsh_p=34, lsh_r=34, lel=44, rsh_p=34, rsh_r=34, rel=44,
            )
            return _seq(((0.0, base), (0.36, arch), (0.64, cushion), (1.0, base)))

        if act == "header":
            jump_h = _clamp(p["action_meta"].get("target_y", 1.34) - 1.18, 0.05, 0.44)
            coil = dict(
                POSES["stand"],
                spine=24, head_p=-8,
                lhip_p=34, lkn=58, rhip_p=34, rkn=58,
                lsh_p=-24, lsh_r=20, lel=30, rsh_p=-24, rsh_r=20, rel=30,
            )
            arch = dict(
                POSES["stand"],
                lift=jump_h, spine=-18, head_p=-18,
                lhip_p=10, lkn=46, rhip_p=18, rkn=52,
                lsh_p=48, lsh_r=34, lel=30, rsh_p=48, rsh_r=34, rel=30,
            )
            snap = dict(
                POSES["stand"],
                lift=jump_h + 0.02, spine=26, head_p=28,
                lhip_p=22, lkn=36, rhip_p=28, rkn=40,
                lsh_p=-16, lsh_r=44, lel=42, rsh_p=-16, rsh_r=44, rel=42,
            )
            land = dict(
                POSES["stand"],
                spine=20, head_p=8,
                lhip_p=28, lkn=46, rhip_p=28, rkn=46,
                lsh_p=24, lsh_r=28, lel=38, rsh_p=24, rsh_r=28, rel=38,
            )
            return _seq(((0.0, base), (0.18, coil), (0.32, arch), (0.44, snap), (0.76, land), (1.0, base)))

        if act == "dive":
            h_norm = _clamp((p["action_meta"].get("target_y", 0.85) - 0.35) / 1.35, 0.0, 1.0)
            fly_lift = 0.05 + 0.48 * h_norm
            fly_body_p = 82.0 - 26.0 * h_norm
            fly_sh_p = 144.0 + 18.0 * h_norm
            fly = dict(
                POSES["stand"],
                lift=fly_lift, body_p=fly_body_p, spine=-10, head_p=-46,
                lsh_p=fly_sh_p, lsh_r=16, lel=10, rsh_p=fly_sh_p, rsh_r=16, rel=10,
                lhip_p=-8, lkn=18, rhip_p=16, rkn=46, lank=22, rank=22,
            )
            land = dict(
                POSES["stand"],
                lift=0.0, body_p=74, spine=-6, head_p=-30,
                lsh_p=84, lsh_r=24, lel=44, rsh_p=84, rsh_r=24, rel=44,
                lhip_p=8, lkn=22, rhip_p=48, rkn=84, lank=16, rank=16,
            )
            push = dict(
                POSES["stand"],
                body_p=28, spine=16, head_p=-10,
                lsh_p=48, lsh_r=22, lel=36, rsh_p=48, rsh_r=22, rel=36,
                lhip_p=24, lkn=38, rhip_p=44, rkn=70,
            )
            return _seq(((0.0, base), (0.18, fly), (0.44, fly), (0.58, land), (0.80, push), (1.0, base)))

        if act == "slide":
            tackle = dict(
                POSES["stand"],
                body_p=-78, spine=12, head_p=32,
                rhip_p=10, rkn=6, rank=12,
                lhip_p=16, lkn=96, lank=18,
                lsh_p=-30, lsh_r=26, lel=14,
                rsh_p=44, rsh_r=32, rel=30,
            )
            sit_up = dict(
                POSES["stand"],
                body_p=-18, spine=26, head_p=10,
                lhip_p=42, lkn=78, rhip_p=36, rkn=58,
                lsh_p=36, lsh_r=20, lel=38, rsh_p=36, rsh_r=20, rel=38,
            )
            return _seq(((0.0, base), (0.16, tackle), (0.52, tackle), (0.76, sit_up), (1.0, base)))

        if act == "parry":
            ty = p["action_meta"].get("target_y", 1.0)
            if ty < 0.60:
                parry = dict(
                    POSES["stand"],
                    spine=30, lhip_p=46, lkn=68, lhip_r=14,
                    rhip_p=46, rkn=68, rhip_r=14,
                    lsh_p=62, lsh_r=44, lel=26, rsh_p=62, rsh_r=44, rel=26,
                )
            elif ty > 1.06:
                parry = dict(
                    POSES["stand"],
                    lift=0.14, spine=-8, lhip_p=16, lkn=24, lhip_r=10,
                    rhip_p=16, rkn=24, rhip_r=10,
                    lsh_p=142, lsh_r=28, lel=18, rsh_p=142, rsh_r=28, rel=18,
                )
            else:
                parry = dict(
                    POSES["stand"],
                    spine=18, lhip_p=34, lkn=48, lhip_r=14,
                    rhip_p=34, rkn=48, rhip_r=14,
                    lsh_p=86, lsh_r=48, lel=24, rsh_p=86, rsh_r=48, rel=24,
                )
            u_hit = _clamp(p["action_hit"] / max(1e-4, p["action_dur"]), 0.15, 0.45)
            w = (u / u_hit) if u <= u_hit else ((1.0 - u) / max(1e-4, 1.0 - u_hit))
            return blend(base, parry, _smooth(w))

        if act == "celebrate":
            if sub == "knee_slide":
                slide_p = dict(
                    POSES["stand"],
                    body_p=6, spine=-18, head_p=-18,
                    lhip_p=18, lkn=104, lank=34,
                    rhip_p=18, rkn=104, rank=34,
                    lsh_p=42, lsh_r=68, lel=16, rsh_p=42, rsh_r=68, rel=16,
                )
                return _seq(((0.0, base), (0.26, base), (0.36, slide_p), (0.78, slide_p), (1.0, base)))
            if sub == "aeroplane":
                wing = dict(
                    base,
                    spine=14, spine_r=10.0 * math.sin(self.t * 5.0),
                    lsh_p=16, lsh_r=82, lel=8,
                    rsh_p=16, rsh_r=82, rel=8,
                )
                w = min(1.0, u / 0.18) * min(1.0, (1.0 - u) / 0.22)
                return blend(base, wing, _smooth(w))
            if sub == "fist_pump":
                hop = 0.22 * abs(math.sin(u * math.pi * 2.0))
                pump = dict(
                    POSES["stand"],
                    spine=-8, lift=hop,
                    lsh_p=138 if u > 0.45 else 24, lsh_r=24, lel=22,
                    rsh_p=154, rsh_r=24, rel=28,
                )
                w = min(1.0, u / 0.15) * min(1.0, (1.0 - u) / 0.20)
                return blend(base, pump, _smooth(w))
            # banter
            point = dict(
                POSES["stand"],
                spine=-4, head_p=-4 + 6.0 * math.sin(self.t * 9.0),
                lsh_p=24, lsh_r=30, lel=68,
                rsh_p=94, rsh_r=8, rel=6,
            )
            w = min(1.0, u / 0.20) * min(1.0, (1.0 - u) / 0.22)
            return blend(base, point, _smooth(w))

        if act == "disbelief":
            oh_no = dict(
                POSES["stand"],
                spine=-6, head_p=-10, head_y=14.0 * math.sin(u * 4.0 * math.pi),
                lsh_p=138, lsh_r=16, lel=108,
                rsh_p=138, rsh_r=16, rel=108,
            )
            w = min(1.0, u / 0.22) * min(1.0, (1.0 - u) / 0.25)
            return blend(base, oh_no, _smooth(w))

        if act == "breather":
            heave = 3.0 * math.sin(self.t * 7.5)
            tired = dict(
                POSES["stand"],
                spine=44.0 + heave, head_p=16.0 - 0.5 * heave,
                lhip_p=14, lkn=30, rhip_p=14, rkn=30,
                lsh_p=38, lsh_r=14, lel=20,
                rsh_p=38, rsh_r=14, rel=20,
            )
            w = min(1.0, u / 0.22) * min(1.0, (1.0 - u) / 0.25)
            return blend(base, tired, _smooth(w))

        return base

    def _compute_pose(self, name):
        from engine3d.rig import solve_look

        p = self.players[name]
        seed = 93.0 if name == "biribel" else 61.0
        base = self._base_locomotion_pose(p, seed)
        pose = self._action_pose(p, base, seed) if p["action"] is not None else base
        act = p["action"]

        # Off-ball call-for-pass wave blends cleanly onto the right arm
        if p["beckon_t"] > 0.0 and p["action"] is None:
            bw = min(1.0, p["beckon_t"] / 0.18) * min(1.0, (0.72 - p["beckon_t"]) / 0.18)
            bw = _clamp(bw, 0.0, 1.0)
            wave = 84.0 + 10.0 * math.sin(self.t * 14.0)
            pose = dict(pose)
            pose["rsh_p"] = pose.get("rsh_p", 0.0) + (wave - pose.get("rsh_p", 0.0)) * bw
            pose["rsh_r"] = pose.get("rsh_r", 0.0) + (28.0 - pose.get("rsh_r", 0.0)) * bw
            pose["rel"] = pose.get("rel", 0.0) + (46.0 - pose.get("rel", 0.0)) * bw

        # Keep authored head arcs during dive/header/chest/disbelief
        keep_head = (
            act in ("header", "chest", "disbelief", "celebrate", "breather")
            or (act == "dive" and p["action_t"] < p["action_dur"] * 0.58)
        )
        if not keep_head:
            px, pz = p["pos"]
            hy, hp = solve_look((px, 1.24, pz), tuple(self.ball_pos), p["yaw"])
            pose["head_y"] = hy * 0.95
            pose["head_p"] = hp * 0.95
        elif act == "celebrate" and p["action_subtype"] == "banter":
            other_name = p["action_meta"].get("other")
            if other_name in self.players:
                ox, oz = self.players[other_name]["pos"]
                hy, hp = solve_look((p["pos"][0], 1.24, p["pos"][1]), (ox, 1.24, oz), p["yaw"])
                pose["head_y"] = hy * 0.85
                pose["head_p"] = hp * 0.85
        return pose

    def player_pose(self, name):
        pose = self.players[name].get("pose")
        if pose is None:
            return self._compute_pose(name)
        return dict(pose)


def _fallback_football(radius=_FootballSim.BALL_R):
    from engine3d.core import Mesh, box

    m = Mesh()
    s = radius * 1.56
    m.add(box(s, s, s, (218, 220, 218), center=(0.0, 0.0, 0.0)))
    m.add(box(s * 1.03, s * 0.48, s * 0.48, (36, 40, 48), center=(0.0, 0.0, 0.0)))
    m.add(box(s * 0.48, s * 1.03, s * 0.48, (36, 40, 48), center=(0.0, 0.0, 0.0)))
    m.add(box(s * 0.48, s * 0.48, s * 1.03, (36, 40, 48), center=(0.0, 0.0, 0.0)))
    return m


def _fallback_goal_post():
    from engine3d.core import Mesh, box

    m = Mesh()
    white, net = (220, 222, 220), (190, 196, 204)
    hw, h, d = _FootballSim.GOAL_HW, _FootballSim.GOAL_H, _FootballSim.GOAL_D
    for sx in (-hw, hw):
        m.add(box(0.11, h, 0.11, white, center=(sx, h * 0.5, 0.0)))
        m.add(box(0.08, 0.08, d, white, center=(sx, 0.04, -d * 0.5)))
        m.add(box(0.07, h, 0.07, net, center=(sx, h * 0.5, -d)))
    m.add(box(hw * 2.0 + 0.11, 0.11, 0.11, white, center=(0.0, h, 0.0)))
    m.add(box(hw * 2.0, 0.07, 0.07, net, center=(0.0, h, -d)))
    return m


def _build_credits_scrim():
    """Soft dark radial-column scrim keeping credits legible over the 3D scene."""
    surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    surf.fill((4, 5, 8, 72))
    cx = WIDTH // 2
    span = 360
    band = pygame.Surface((span * 2, 1), pygame.SRCALPHA)
    for dx in range(-span, span):
        k = 1.0 - abs(dx) / float(span)
        band.set_at((dx + span, 0), (4, 5, 8, int(150 * max(0.0, k) ** 1.6)))
    surf.blit(pygame.transform.scale(band, (span * 2, HEIGHT)), (cx - span, 0))
    return surf


class _FootballScene:
    """Lazy 3D pasture pitch renderer for the ending credits."""

    RES = (640, 448)
    _PUFF_COLS = ((118, 96, 68), (82, 108, 58), (222, 224, 212))
    _PUFF_RADS = (2, 3, 5, 7)

    _KITS = {
        "biribel": dict(
            scale=0.74, bulk=0.84, head_scale=1.24, head_w=1.02,
            stubble=False, brow_t=2,
            jacket=(48, 80, 122), inner=(186, 184, 174), cuff=(180, 178, 168),
            vest=None, belt=None, buckle=None, pouches=False,
            armband=None, accent=None, glove=None,
            lapel=None, shirt=None, tie=None,
            pants=(30, 44, 70),
            boots=(30, 32, 38), sole=(196, 192, 180),
        ),
        "bodi": dict(
            scale=0.72, bulk=0.82, head_scale=1.24, head_w=1.02,
            stubble=False, brow_t=2,
            jacket=(148, 66, 52), vest=None, belt=None, buckle=None,
            pouches=False, armband=None, accent=None, glove=None,
            plaid=None, inner=None, boots_h=None,
            lapel=None, shirt=None, tie=None, cuff=None,
            crew=True, sleeves="short",
            print=("stripe", (190, 182, 162), (76, 40, 34)),
            shorts=True, pants=(60, 74, 98),
            socks=(182, 178, 168), sock_h=0.10,
            boots=(34, 38, 44), sole=(194, 190, 178),
        ),
    }

    def __init__(self):
        self._r = None
        self._hums = {}
        self._ball_mesh = None
        self._ball_rows = None
        self._ball_faces = None
        self._flag_mesh = None
        self._flag_faces = None
        self._puff_surfs = None
        self._surf = None
        self._scrim = None
        self._failed = False

    def _load_assets(self):
        from engine3d.core import Mesh
        from game.render3d_bridge import load_mesh_asset

        try:
            verts, faces = load_mesh_asset("football")
            ball = Mesh()
            ball.verts = [tuple(float(c) for c in v) for v in verts]
            ball.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in faces]
        except Exception:
            traceback.print_exc()
            ball = _fallback_football()

        try:
            verts, faces = load_mesh_asset("goal_post")
            goal = Mesh()
            goal.verts = [tuple(float(c) for c in v) for v in verts]
            goal.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in faces]
        except Exception:
            traceback.print_exc()
            goal = _fallback_goal_post()
        return ball, goal

    def _build_pitch(self, r, goal_mesh):
        from cutscenes import m7world3d as W7
        from engine3d.core import Mesh, box, quad_xz, rot_y

        grass = W7._t("grass", (60, 78, 46))
        r.bake(quad_xz(-120.0, -120.0, 120.0, 120.0, 0.0, grass, layer=0, seg=18.0))

        # Mowed pitch stripes + worn goalmouth dirt + chalk markings
        pitch = Mesh()
        stripe_a = W7._t("grass", (68, 90, 50))
        stripe_b = W7._t("grass", (56, 74, 42))
        hx, hz = _FootballSim.PITCH_HX, _FootballSim.PITCH_HZ
        for i in range(8):
            x0 = -hx - 0.6 + i * ((hx + 0.6) * 2.0 / 8.0)
            x1 = x0 + ((hx + 0.6) * 2.0 / 8.0)
            pitch.add(
                quad_xz(
                    x0, -hz - 0.4, x1, hz + 0.4, 0.012,
                    stripe_a if i % 2 == 0 else stripe_b, layer=1, seg=4.0,
                )
            )
        dirt = W7._t("dirt", (98, 80, 56))
        for side in (-1.0, 1.0):
            a, b = sorted((side * (hx - 1.3), side * (hx + 1.2)))
            pitch.add(quad_xz(a, -1.65, b, 1.65, 0.018, dirt, layer=1, seg=2.0))

        chalk = (206, 208, 198)
        pitch.add(box(hx * 2.0 + 0.08, 0.012, 0.08, chalk, center=(0.0, 0.022, hz), layer=1))
        pitch.add(box(hx * 2.0 + 0.08, 0.012, 0.08, chalk, center=(0.0, 0.022, -hz), layer=1))
        pitch.add(box(0.08, 0.012, hz * 2.0, chalk, center=(-hx, 0.022, 0.0), layer=1))
        pitch.add(box(0.08, 0.012, hz * 2.0, chalk, center=(hx, 0.022, 0.0), layer=1))
        pitch.add(box(0.08, 0.012, hz * 2.0, chalk, center=(0.0, 0.022, 0.0), layer=1))
        for side in (-1.0, 1.0):
            bx_in = side * (hx - 2.3)
            pitch.add(box(0.07, 0.012, 5.2, chalk, center=(bx_in, 0.022, 0.0), layer=1))
            for sz in (-2.6, 2.6):
                pitch.add(box(2.3, 0.012, 0.07, chalk, center=(side * (hx - 1.15), 0.022, sz), layer=1))
        rad = 1.65
        for k in range(16):
            a0, a1 = math.tau * k / 16.0, math.tau * (k + 1) / 16.0
            ax, az = rad * math.cos(a0), rad * math.sin(a0)
            bx_c, bz_c = rad * math.cos(a1), rad * math.sin(a1)
            seg_len = math.hypot(bx_c - ax, bz_c - az)
            yaw = -math.degrees(math.atan2(bz_c - az, bx_c - ax))
            pitch.add(
                box(seg_len + 0.02, 0.012, 0.07, chalk, layer=1),
                rot_y(yaw),
                (0.5 * (ax + bx_c), 0.022, 0.5 * (az + bz_c)),
            )
        # Corner flagpoles (pennants flutter dynamically in draw)
        pole_col = (212, 214, 206)
        for sx in (-hx, hx):
            for sz in (-hz, hz):
                pitch.add(box(0.04, 0.92, 0.04, pole_col, center=(sx, 0.46, sz), layer=2))
        r.bake(pitch)

        # Both imported goalposts on the goal lines (mouths facing centre pitch).
        r.bake(goal_mesh, rot_y(90.0), (-hx, 0.0, 0.0))
        r.bake(goal_mesh, rot_y(-90.0), (hx, 0.0, 0.0))

        # Country pasture surround: post-and-rail fences, trees, hay bales, far ridge.
        scenery = Mesh()
        scenery.add(W7._fence(-12.5, 6.2, 12.5, 6.2, h=1.05, every=2.5))
        scenery.add(W7._fence(-12.5, -2.0, -12.5, 6.2, h=1.05, every=2.5))
        scenery.add(W7._fence(12.5, -2.0, 12.5, 6.2, h=1.05, every=2.5))
        scenery.add(W7._hedgerow(-22.0, 10.5, 22.0, 10.5, seed=17))
        for i, (tx, tz) in enumerate((
            (-15.5, 8.0), (-11.0, 13.5), (-4.5, 15.0), (3.8, 14.2),
            (11.4, 12.8), (16.0, 7.6), (-18.5, 1.5), (18.5, 2.0),
        )):
            maker = (W7.tree, W7._shelter_tree, W7._walnut)[i % 3]
            scenery.add(maker(20 + i), rot_y(i * 53.0), (tx, 0.0, tz))
        scenery.add(W7.hay(3), rot_y(14.0), (-11.0, 0.0, 8.2))
        scenery.add(W7.hay(2), rot_y(-12.0), (11.2, 0.0, 8.0))
        scenery.add(W7._farm_windpump(), t=(15.5, 0.0, 19.0))
        for i in range(18):
            a = math.pi * (0.04 + 0.92 * i / 17.0)
            rad_h = 74.0 + (i % 3) * 8.0
            scenery.add(
                W7._bipyr(
                    rad_h * math.cos(a), 0.0, rad_h * math.sin(a),
                    24.0, 10.0 + (i * 5 % 6), 1.0, (34, 42, 40), n=6,
                )
            )
        r.bake(scenery)

    def _build_puff_cache(self):
        cache = {}
        alphas = (52, 96, 142)
        for ci, col in enumerate(self._PUFF_COLS):
            for ti, rad in enumerate(self._PUFF_RADS):
                sz = rad * 2 + 2
                for bi, alpha in enumerate(alphas):
                    s = pygame.Surface((sz, sz), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*col, alpha), (rad + 1, rad + 1), rad)
                    cache[(ci, ti, bi)] = s
        return cache

    def _ensure(self):
        if self._r is not None:
            return True
        if self._failed:
            return False
        try:
            from engine3d import Renderer
            from engine3d.core import Light, box

            r = Renderer(
                self.RES[0], self.RES[1],
                fog=(128, 108, 108), fog_start=26.0, fog_end=150.0,
            )
            r.light = Light(
                direction=(0.62, 0.42, 0.56), ambient=0.44, diffuse=0.58,
                sky=0.10, tint=(0.98, 0.86, 0.74),
            )
            ball, goal = self._load_assets()
            self._build_pitch(r, goal)
            self._ball_mesh = ball
            self._ball_faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in ball.faces]
            if hasattr(r, "pack"):
                self._ball_rows = r.pack(ball.verts, self._ball_faces)
            self._flag_mesh = box(0.24, 0.14, 0.02, (194, 72, 42), center=(0.12, 0.84, 0.0))
            self._flag_faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in self._flag_mesh.faces]
            self._puff_surfs = self._build_puff_cache()
            self._surf = pygame.Surface((WIDTH, HEIGHT))
            self._scrim = _build_credits_scrim()
            self._r = r
            return True
        except Exception:
            traceback.print_exc()
            self._failed = True
            return False

    def _draw_ball(self, r, sim):
        bx, by, bz = sim.ball_pos
        M = sim.ball_mat
        if hasattr(r, "add_packed") and self._ball_rows is not None:
            import numpy as np

            rt = np.array(M, dtype=self._ball_rows.dtype).reshape(3, 3).T
            out = self._ball_rows.copy()
            out[:, 0:3] = self._ball_rows[:, 0:3] @ rt
            out[:, 0] += bx
            out[:, 1] += by
            out[:, 2] += bz
            out[:, 6:9] = self._ball_rows[:, 6:9] @ rt
            r.add_packed(out)
        else:
            from engine3d.core import m_apply

            verts = [
                (bx + q[0], by + q[1], bz + q[2])
                for v in self._ball_mesh.verts
                for q in (m_apply(M, v),)
            ]
            r.add_dynamic(verts, self._ball_faces)
        h = max(0.0, by - sim.BALL_R)
        r.add_blob_shadow((bx, 0.024, bz), 0.22, 0.22, 0.36 * max(0.22, 1.0 - h * 0.28), layer=1)

    def _draw_flags(self, r, sim):
        from engine3d.core import m_apply, rot_y

        hx, hz = _FootballSim.PITCH_HX, _FootballSim.PITCH_HZ
        for idx, (sx, sz) in enumerate(((-hx, -hz), (hx, -hz), (-hx, hz), (hx, hz))):
            flutter = 14.0 * math.sin(sim.t * 4.2 + idx * 1.4) + 6.0 * math.sin(sim.t * 9.5 + idx)
            m = rot_y(18.0 + flutter)
            verts = [
                (sx + q[0], q[1], sz + q[2])
                for v in self._flag_mesh.verts
                for q in (m_apply(m, v),)
            ]
            r.add_dynamic(verts, self._flag_faces)

    def _draw_puffs(self, r, sim):
        from cutscenes import m6fx3d as _fx

        if not sim.puffs or not self._puff_surfs:
            return
        surfs = self._puff_surfs
        for pf in sim.puffs:
            px, py, pz, _, _, _, age, life, tier, ci = pf
            fade = 1.0 - age / life
            if fade <= 0.05:
                continue
            bi = 2 if fade > 0.66 else (1 if fade > 0.33 else 0)
            sp = surfs.get((ci, tier, bi))
            if sp is None:
                continue

            def _blit_puff(surf, sx, sy, _ppm, _z, img=sp):
                surf.blit(img, (int(sx) - img.get_width() // 2, int(sy) - img.get_height() // 2))

            r.add_sprite((px, py, pz), _blit_puff, layer=_fx.FX_LAYER)

    def _player_hum(self, name):
        h = self._hums.get(name)
        if h is None:
            from cutscenes.cast3d import spec3d
            from engine3d.core import box
            from engine3d.rig import Humanoid

            class _KickaboutHumanoid(Humanoid):
                def _scale_part(self, key, hs):
                    verts, faces = self._parts[key]
                    self._parts[key] = (
                        [(x * hs, y * hs, z * hs) for x, y, z in verts],
                        faces,
                    )

                def _build_parts(self):
                    super()._build_parts()
                    s = self.spec
                    if s.get("shorts"):
                        skin, pants = s["skin"], s["pants"]
                        self._parts["thigh"] = self._flatten([
                            box(0.166, 0.26, 0.176, pants, center=(0, -0.13, 0)),
                            box(0.132, 0.19, 0.140, skin, center=(0, -0.355, 0)),
                        ])
                        sh = max(0.0, min(0.32, float(s.get("sock_h") or 0.0)))
                        if s.get("socks") and sh > 0.0:
                            bare_h = 0.45 - sh
                            shin = [
                                box(0.128, bare_h, 0.138, skin, center=(0, -bare_h * 0.5, 0)),
                                box(0.136, sh, 0.146, s["socks"], center=(0, -0.45 + sh * 0.5, 0)),
                            ]
                            if s.get("sock_trim"):
                                shin.append(box(0.142, 0.024, 0.152, s["sock_trim"],
                                                center=(0, -0.45 + sh - 0.012, 0)))
                        else:
                            shin = [box(0.128, 0.45, 0.138, skin, center=(0, -0.225, 0))]
                        self._parts["shin"] = self._flatten(shin)
                        self._uniq = None
                    hs = float(s.get("head_scale") or 1.0)
                    if hs != 1.0:
                        for key in ("head", "face", "face2"):
                            self._scale_part(key, hs)
                        self._uniq = None

                def set_expression(self, name=None, mouth_open=None):
                    super().set_expression(name, mouth_open)
                    hs = float(self.spec.get("head_scale") or 1.0)
                    if hs != 1.0:
                        for key in ("face", "face2"):
                            self._scale_part(key, hs)
                        self._uniq = None

            h = self._hums[name] = _KickaboutHumanoid(spec3d(name, **self._KITS[name]))
            h._gl_spec_key = repr(sorted(h.spec.items())) + "|kid"
        return h

    def _draw_player(self, r, _w, name, pl, pose, t_ms, seed):
        h = self._player_hum(name)
        expr = pl["expr"] or "neutral"
        mouth = pl["mouth"] or 0.0
        face_key = (expr, round(mouth, 2) if mouth else 0.0)
        if getattr(h, "_m6_face", None) != face_key:
            h.set_expression(expr, mouth)
            h._m6_face = face_key
        p = _w.life_pose(pose, t_ms, 0.25, seed)
        pos = (pl["pos"][0], 0.0, pl["pos"][1])
        joints = r.add_humanoid(h, p, pos, pl["yaw"], rifle_on=False)
        if len(_w.LAST) < 16:
            _w.LAST.append({"key": name, "joints": joints, "pos": pos,
                            "yaw": pl["yaw"], "pose": p, "hd": False,
                            "flags": (), "rifle": False})

    def draw(self, surface, sim):
        if not self._ensure():
            return False
        from cutscenes import m5fx3d as _m5fx
        from cutscenes import m6fx3d as _fx
        from cutscenes import m6world3d as _w
        from missions.m8.revenge import chase_set as _cs

        r = self._r
        t_ms = int(sim.t * 1000.0)
        shk_x = shk_y = 0.0
        if sim.clang_t > 0.0 and not getattr(STATE, "reduced_motion", False):
            amp = 0.026 * (sim.clang_t / 0.22)
            shk_x = amp * math.sin(sim.t * 72.0)
            shk_y = amp * 0.6 * math.cos(sim.t * 88.0)
        tgt_y = 0.84 + _clamp((sim.ball_pos[1] - 0.4) * 0.15, 0.0, 0.3)
        r.set_camera(
            (sim.cam_x + shk_x, 1.08 + sim.cam_d * 0.11 + shk_y, sim.tgt_z - sim.cam_d),
            (sim.tgt_x, tgt_y, sim.tgt_z),
            sim.cam_fov,
            0.0,
        )
        _m5fx.night_sky(
            r, r.surface, t_ms, (26, 36, 62), (168, 114, 90),
            stars=14, moon=False, clouds=0, sodium=(84, 52, 34), mist=None, seed=19,
        )
        _cs.stratus(r, r.surface, t_ms, {
            "key": "credits_dusk",
            "hor": (168, 114, 90),
            "sun": (0.62, 0.42, 0.56),
            "rim": ((196, 130, 108), (242, 186, 144)),
            "body": (120, 108, 126),
        })
        r.begin()
        r.add_static()
        r.add_sprite(
            (44.0, 6.8, 46.0),
            _fx.glow((255, 184, 116), 14.0, t_ms, intensity=0.52, core=(255, 224, 178), max_px=68),
            layer=_fx.FX_LAYER,
        )

        del _w.LAST[:]
        biri = sim.players["biribel"]
        bodi = sim.players["bodi"]
        self._draw_player(r, _w, "biribel", biri, sim.player_pose("biribel"), t_ms, 93)
        self._draw_player(r, _w, "bodi", bodi, sim.player_pose("bodi"), t_ms, 61)
        self._draw_flags(r, sim)
        self._draw_ball(r, sim)
        self._draw_puffs(r, sim)

        buf = r.surface
        r.flush(buf)
        try:
            _fx.grade_cine(buf)
        except Exception:
            pass
        _fx.present_crisp(buf, self._surf)
        surface.blit(self._surf, (0, 0))
        surface.blit(self._scrim, (0, 0))
        return True
