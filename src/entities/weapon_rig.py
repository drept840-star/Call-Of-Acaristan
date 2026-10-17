
"""The three weapon rigs, as drawable-on-call functions.

Lifted verbatim out of Player.draw(). Body geometry is untouched - the only
substitutions are colour literals becoming finish roles and the three
identical nested quad() closures becoming one module-level helper.

They live here rather than staying inline for two reasons:

  * Player.draw() was already ~680 lines and customization adds gear to it.
  * The Outfitter has to show you a weapon finish before you buy it, which
    means drawing a rig with no body attached. That is only honest if the shop
    runs the production rig code - a second hand-drawn preview sprite would
    drift from the gun you actually equip, and the shop would promise something
    the game does not deliver.

ctx carries exactly the values each block used to close over in draw():
grip_x, grip_y, arm_dx, arm_dy, raise_factor, reload_active, reload_progress.
g is one gun's resolved {role: rgb} map from core.appearance.resolve().
"""
import math
import pygame

from engine.render2d import SurfacePen as _SurfacePen  # RPE6 B-033: Pen sink (facade only, E4)


def quad(ax, ay, bx, by, rear_w, front_w, pdx, pdy):
    """A tapered quad along the gun axis - the receiver/handguard cross-section.

    rear_w/front_w are the half-widths at each end, and pdx/pdy is the
    perpendicular to the barrel. Every rig built its own copy of this; one
    shared version is the only edit these bodies ever received.
    """
    return [
        (ax - pdx * rear_w, ay - pdy * rear_w),
        (ax + pdx * rear_w, ay + pdy * rear_w),
        (bx + pdx * front_w, by + pdy * front_w),
        (bx - pdx * front_w, by - pdy * front_w),
    ]


def draw_os12(pen, ctx, g):
    """OS 12 assault rifle - AK-47 offspring."""
    grip_x = ctx["grip_x"]
    grip_y = ctx["grip_y"]
    arm_dx = ctx["arm_dx"]
    arm_dy = ctx["arm_dy"]
    raise_factor = ctx["raise_factor"]
    reload_active = ctx["reload_active"]
    reload_progress = ctx["reload_progress"]

    draw_gun_len = int(26.0 * (1.0 - raise_factor * 0.35))

    gun_start_x = grip_x + arm_dx * 2
    gun_start_y = grip_y + arm_dy * 2
    gun_end_x = grip_x + arm_dx * draw_gun_len
    gun_end_y = grip_y + arm_dy * draw_gun_len

    perp_dx = -arm_dy
    perp_dy = arm_dx

    # Receiver body - longer and chunkier than the pistol
    receiver = quad(gun_start_x, gun_start_y, gun_end_x, gun_end_y,
                    3.8, 2.8, perp_dx, perp_dy)
    pen.polygon( g["receiver"], receiver)

    # Top cover / dust cover - slightly raised, metal grey
    cover_sx = gun_start_x + arm_dx * 3 - perp_dx * 2.0
    cover_sy = gun_start_y + arm_dy * 3 - perp_dy * 2.0
    cover_ex = gun_end_x - arm_dx * 4 - perp_dx * 1.6
    cover_ey = gun_end_y - arm_dy * 4 - perp_dy * 1.6
    cover = quad(cover_sx, cover_sy, cover_ex, cover_ey, 2.4, 1.8,
                 perp_dx, perp_dy)
    pen.polygon( g["cover"], cover)
    pen.polygon( g["cover_edge"], cover, 1)

    # Wooden handguard - warm brown, distinct from the metal
    hg_sx = gun_start_x + arm_dx * 8
    hg_sy = gun_start_y + arm_dy * 8
    hg_ex = gun_start_x + arm_dx * 18
    hg_ey = gun_start_y + arm_dy * 18
    handguard = quad(hg_sx, hg_sy, hg_ex, hg_ey, 3.6, 3.0, perp_dx, perp_dy)
    pen.polygon( g["wood"], handguard)
    pen.polygon( g["wood_edge"], handguard, 1)

    # Barrel - extends past the handguard
    barrel_start_x = gun_end_x - arm_dx * 5
    barrel_start_y = gun_end_y - arm_dy * 5
    muzzle_x = gun_end_x + arm_dx * 3
    muzzle_y = gun_end_y + arm_dy * 3
    pen.line( g["barrel"],
        (barrel_start_x, barrel_start_y), (muzzle_x, muzzle_y), 3,
    )
    # Muzzle brake - wider end
    mb_x = muzzle_x + arm_dx * 2
    mb_y = muzzle_y + arm_dy * 2
    pen.line( g["muzzle"],
        (muzzle_x, muzzle_y), (mb_x, mb_y), 5,
    )
    pen.line( g["groove"],
        (muzzle_x + perp_dx * 2.5, muzzle_y + perp_dy * 2.5),
        (mb_x + perp_dx * 2.5, mb_y + perp_dy * 2.5), 1,
    )
    pen.line( g["groove"],
        (muzzle_x - perp_dx * 2.5, muzzle_y - perp_dy * 2.5),
        (mb_x - perp_dx * 2.5, mb_y - perp_dy * 2.5), 1,
    )
    # Bore
    pen.circle( g["bore"], (int(mb_x), int(mb_y)), 2)

    # Front sight post
    fs_x = gun_end_x - arm_dx * 2
    fs_y = gun_end_y - arm_dy * 2
    pen.line( g["front_sight"],
        (fs_x - perp_dx * 3.5, fs_y - perp_dy * 3.5),
        (fs_x + perp_dx * 1.0, fs_y + perp_dy * 1.0), 2,
    )

    # Magazine - curved banana mag, the iconic AK silhouette
    # During reload: mag drops out (0.00-0.30), is absent (0.30-0.60),
    # then rocks into the magwell (0.60-1.00).
    _mag_visible = True
    _mag_drop_off = 0.0
    _mag_along_off = 0.0
    if reload_active:
        rp = reload_progress
        if rp < 0.30:
            t = rp / 0.30
            _mag_drop_off = t * 10.0
            _mag_along_off = -t * 2.0
            if t > 0.85:
                _mag_visible = False
        elif rp < 0.60:
            _mag_visible = False
        else:
            t = (rp - 0.60) / 0.40
            ease = 1.0 - (1.0 - t) * (1.0 - t)
            _mag_drop_off = (1.0 - ease) * 8.0
            _mag_along_off = (1.0 - ease) * 3.0

    if _mag_visible:
        mag_attach_x = gun_start_x + arm_dx * 6 + arm_dx * _mag_along_off
        mag_attach_y = gun_start_y + arm_dy * 6 + arm_dy * _mag_along_off
        mag_mid_x = (mag_attach_x
                     + perp_dx * (6 + _mag_drop_off) - arm_dx * 2)
        mag_mid_y = (mag_attach_y
                     + perp_dy * (6 + _mag_drop_off) - arm_dy * 2)
        mag_tip_x = (mag_attach_x
                     + perp_dx * (12 + _mag_drop_off) - arm_dx * 5)
        mag_tip_y = (mag_attach_y
                     + perp_dy * (12 + _mag_drop_off) - arm_dy * 5)
        # Left edge
        mag_left = [
            (mag_attach_x - perp_dx * 2.2, mag_attach_y - perp_dy * 2.2),
            (mag_mid_x - perp_dx * 1.8, mag_mid_y - perp_dy * 1.8),
            (mag_tip_x - perp_dx * 2.0, mag_tip_y - perp_dy * 2.0),
        ]
        # Right edge
        mag_right = [
            (mag_attach_x + perp_dx * 2.2, mag_attach_y + perp_dy * 2.2),
            (mag_mid_x + perp_dx * 1.8, mag_mid_y + perp_dy * 1.8),
            (mag_tip_x + perp_dx * 2.0, mag_tip_y + perp_dy * 2.0),
        ]
        mag_poly = mag_left + list(reversed(mag_right))
        pen.polygon( g["mag"], mag_poly)
        pen.polygon( g["mag_edge"], mag_poly, 1)
        # Magazine ridges (two subtle lines)
        for ridge_t in (0.35, 0.65):
            r1x = mag_attach_x + (mag_tip_x - mag_attach_x) * ridge_t - perp_dx * 2.1
            r1y = mag_attach_y + (mag_tip_y - mag_attach_y) * ridge_t - perp_dy * 2.1
            r2x = mag_attach_x + (mag_tip_x - mag_attach_x) * ridge_t + perp_dx * 2.1
            r2y = mag_attach_y + (mag_tip_y - mag_attach_y) * ridge_t + perp_dy * 2.1
            pen.line( g["mag_ridge"], (r1x, r1y), (r2x, r2y), 1)

    # Grip / pistol grip - angled more steeply than the pistol's
    grip_base_x = gun_start_x - arm_dx * 1 + perp_dx * 3
    grip_base_y = gun_start_y - arm_dy * 1 + perp_dy * 3
    grip_end_x = grip_base_x - arm_dx * 5 + perp_dx * 6
    grip_end_y = grip_base_y - arm_dy * 5 + perp_dy * 6
    pen.line( g["wood"],  # wooden grip
        (grip_base_x, grip_base_y), (grip_end_x, grip_end_y), 5,
    )
    pen.line( g["wood_edge"],
        (grip_base_x, grip_base_y), (grip_end_x, grip_end_y), 1,
    )

    # Rear sight notch (simple)
    rs_x = gun_start_x + arm_dx * 5 - perp_dx * 3.0
    rs_y = gun_start_y + arm_dy * 5 - perp_dy * 3.0
    pen.line( g["muzzle"],
        (rs_x - arm_dx * 1.5, rs_y - arm_dy * 1.5),
        (rs_x + arm_dx * 1.5, rs_y + arm_dy * 1.5), 2,
    )

    # Stock stub - short, wooden, visible behind the grip
    stock_sx = gun_start_x - arm_dx * 3
    stock_sy = gun_start_y - arm_dy * 3
    stock_ex = gun_start_x - arm_dx * 10
    stock_ey = gun_start_y - arm_dy * 10
    pen.line( g["wood"],
        (stock_sx + perp_dx * 2, stock_sy + perp_dy * 2),
        (stock_ex + perp_dx * 3.5, stock_ey + perp_dy * 3.5), 5,
    )
    pen.line( g["wood_edge"],
        (stock_sx + perp_dx * 2, stock_sy + perp_dy * 2),
        (stock_ex + perp_dx * 3.5, stock_ey + perp_dy * 3.5), 1,
    )


def draw_k9(pen, ctx, g):
    """K-9 suppressed SMG / compact PDW.

    Keep this intentionally compact. The first pass was longer than the rifle
    silhouette, so it read like an LMG. The K-9 is a short black-site PDW:
    stubby receiver, compact suppressor, collapsed wire stock, straight stick
    mag.
    """
    grip_x = ctx["grip_x"]
    grip_y = ctx["grip_y"]
    arm_dx = ctx["arm_dx"]
    arm_dy = ctx["arm_dy"]
    raise_factor = ctx["raise_factor"]
    reload_active = ctx["reload_active"]
    reload_progress = ctx["reload_progress"]

    draw_gun_len = int(18.0 * (1.0 - raise_factor * 0.30))
    gun_start_x = grip_x + arm_dx * 1
    gun_start_y = grip_y + arm_dy * 1
    gun_end_x = grip_x + arm_dx * draw_gun_len
    gun_end_y = grip_y + arm_dy * draw_gun_len
    perp_dx = -arm_dy
    perp_dy = arm_dx

    # Compact receiver/body.
    rec_end_x = gun_end_x - arm_dx * 3
    rec_end_y = gun_end_y - arm_dy * 3
    receiver = quad(gun_start_x, gun_start_y, rec_end_x, rec_end_y,
                    3.0, 2.4, perp_dx, perp_dy)
    pen.polygon( g["receiver"], receiver)
    pen.polygon( g["receiver_edge"], receiver, 1)
    pen.line( g["receiver_shine"],
                     (gun_start_x + arm_dx * 3 - perp_dx * 1.8,
                      gun_start_y + arm_dy * 3 - perp_dy * 1.8),
                     (rec_end_x - arm_dx * 2 - perp_dx * 1.3,
                      rec_end_y - arm_dy * 2 - perp_dy * 1.3), 1)

    # Short integral suppressor - visible, but not rifle-length.
    sup_start_x = gun_end_x - arm_dx * 4
    sup_start_y = gun_end_y - arm_dy * 4
    sup_end_x = gun_end_x + arm_dx * 5
    sup_end_y = gun_end_y + arm_dy * 5
    pen.line( g["can"], (sup_start_x, sup_start_y), (sup_end_x, sup_end_y), 4)
    pen.line( g["can_shine"],
                     (sup_start_x - perp_dx * 1.4, sup_start_y - perp_dy * 1.4),
                     (sup_end_x - perp_dx * 1.4, sup_end_y - perp_dy * 1.4), 1)
    pen.circle( g["bore"], (int(sup_end_x), int(sup_end_y)), 2)

    # Collapsed wire stock: reads as folded, not a long shoulder stock.
    stock_root = (gun_start_x - arm_dx * 1 + perp_dx * 1.5,
                  gun_start_y - arm_dy * 1 + perp_dy * 1.5)
    stock_tip = (gun_start_x - arm_dx * 7 + perp_dx * 2.2,
                 gun_start_y - arm_dy * 7 + perp_dy * 2.2)
    pen.line( g["stock"], stock_root, stock_tip, 2)
    pen.circle( g["stock_knob"], (int(stock_tip[0]), int(stock_tip[1])), 2)

    # Pistol grip, short and close to the receiver.
    grip_base_x = gun_start_x + perp_dx * 2.8
    grip_base_y = gun_start_y + perp_dy * 2.8
    grip_end_x = grip_base_x - arm_dx * 2 + perp_dx * 5.4
    grip_end_y = grip_base_y - arm_dy * 2 + perp_dy * 5.4
    pen.line( g["grip"], (grip_base_x, grip_base_y), (grip_end_x, grip_end_y), 4)
    pen.line( g["grip_shine"], (grip_base_x, grip_base_y), (grip_end_x, grip_end_y), 1)

    # Straight stick magazine. Shorter than before so it doesn't read
    # as an LMG box/drum dangling under a long gun.
    mag_visible = True
    mag_drop = 0.0
    mag_along = 0.0
    slap_offset = 0.0
    if reload_active:
        rp = reload_progress
        if rp < 0.22:
            t = rp / 0.22
            mag_drop = t * 12.0
            mag_along = -t * 1.5
        elif rp < 0.58:
            mag_visible = False
        elif rp < 0.78:
            t = (rp - 0.58) / 0.20
            mag_drop = (1.0 - t) * 11.0
            mag_along = (1.0 - t) * 3.0
            slap_offset = math.sin(t * math.pi) * 2.0
        else:
            t = (rp - 0.78) / 0.22
            mag_drop = (1.0 - t) * 2.5
    if mag_visible:
        mag_attach_x = gun_start_x + arm_dx * 6 + arm_dx * mag_along
        mag_attach_y = gun_start_y + arm_dy * 6 + arm_dy * mag_along
        mag_tip_x = mag_attach_x + perp_dx * (10 + mag_drop + slap_offset)
        mag_tip_y = mag_attach_y + perp_dy * (10 + mag_drop + slap_offset)
        mag_poly = [
            (mag_attach_x - perp_dx * 1.7, mag_attach_y - perp_dy * 1.7),
            (mag_attach_x + perp_dx * 1.7, mag_attach_y + perp_dy * 1.7),
            (mag_tip_x + perp_dx * 2.1, mag_tip_y + perp_dy * 2.1),
            (mag_tip_x - perp_dx * 2.1, mag_tip_y - perp_dy * 2.1),
        ]
        pen.polygon( g["mag"], mag_poly)
        pen.polygon( g["mag_edge"], mag_poly, 1)
        pen.line( g["mag_line"],
                         (mag_attach_x, mag_attach_y), (mag_tip_x, mag_tip_y), 1)


def draw_pistol(pen, ctx, g):
    """The original service pistol."""
    grip_x = ctx["grip_x"]
    grip_y = ctx["grip_y"]
    arm_dx = ctx["arm_dx"]
    arm_dy = ctx["arm_dy"]
    raise_factor = ctx["raise_factor"]

    draw_gun_len = int(18.0 * (1.0 - raise_factor * 0.35))

    gun_start_x = grip_x + arm_dx * 2
    gun_start_y = grip_y + arm_dy * 2
    gun_end_x = grip_x + arm_dx * draw_gun_len
    gun_end_y = grip_y + arm_dy * draw_gun_len

    perp_dx = -arm_dy
    perp_dy = arm_dx

    # Main pistol frame
    frame = quad(gun_start_x, gun_start_y, gun_end_x, gun_end_y,
                 3.2, 2.3, perp_dx, perp_dy)
    pen.polygon( g["frame"], frame)

    # Slide, slightly offset upward
    slide_start_x = gun_start_x + arm_dx * 1.5 - perp_dx * 1.5
    slide_start_y = gun_start_y + arm_dy * 1.5 - perp_dy * 1.5
    slide_end_x = gun_end_x - arm_dx * 2 - perp_dx * 1.2
    slide_end_y = gun_end_y - arm_dy * 2 - perp_dy * 1.2
    slide = quad(slide_start_x, slide_start_y, slide_end_x, slide_end_y,
                 2.2, 1.7, perp_dx, perp_dy)
    pen.polygon( g["slide"], slide)
    pen.polygon( g["slide_edge"], slide, 1)

    # Short barrel / muzzle
    muzzle_x = gun_end_x + arm_dx * 2
    muzzle_y = gun_end_y + arm_dy * 2
    pen.line( g["barrel"],
        (gun_end_x, gun_end_y), (muzzle_x, muzzle_y), 3,
    )
    pen.circle( g["bore"], (int(muzzle_x), int(muzzle_y)), 2)

    # Grip angled downward/back
    grip_base_x = gun_start_x - arm_dx * 2 + perp_dx * 3
    grip_base_y = gun_start_y - arm_dy * 2 + perp_dy * 3
    grip_end_x = grip_base_x - arm_dx * 4 + perp_dx * 5
    grip_end_y = grip_base_y - arm_dy * 4 + perp_dy * 5
    pen.line( g["grip"],
        (grip_base_x, grip_base_y), (grip_end_x, grip_end_y), 5,
    )

    # Tiny trigger guard
    tg_x = gun_start_x + arm_dx * 4 + perp_dx * 2.5
    tg_y = gun_start_y + arm_dy * 4 + perp_dy * 2.5
    pen.circle( g["grip"], (int(tg_x), int(tg_y)), 3, 1)

    # Small red optic dot
    dot_x = gun_start_x + arm_dx * 9 - perp_dx * 3
    dot_y = gun_start_y + arm_dy * 9 - perp_dy * 3
    pen.circle( g["optic"], (int(dot_x), int(dot_y)), 1)


# Rig name -> (draw fn, gun key in core.appearance.GUN_BASE).
# The rig names are what Player.rig_weapon_name() returns; the gun keys are
# what an appearance indexes finishes by. They differ only for the K-9.
RIGS = {
    "os12": (draw_os12, "os12"),
    "k9_smg": (draw_k9, "k9"),
    "pistol": (draw_pistol, "pistol"),
}


def draw(surface, rig_name, ctx, rigs, pen=None):
    """Draw *rig_name* with the finishes in *rigs*.

    Unknown rig falls back to the pistol, which is what the inline if/elif/else
    it replaced did: the else branch was the pistol, so a junk rig name drew a
    pistol rather than nothing.
    """
    fn, gun_key = RIGS.get(rig_name) or RIGS["pistol"]
    fn(pen if pen is not None else _SurfacePen(surface), ctx, rigs[gun_key])
