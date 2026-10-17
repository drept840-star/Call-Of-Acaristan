"""prompt - the world-anchored interaction tag ("[E] ...") drawn over a spot.

Phase 4: the body moved verbatim from ``missions.m3.draw._draw_prompt_tag``
(the defaults are M3's look) and ``missions.m5.decor.draw_prompt`` migrated onto
it (M5 passes its own chrome and turns the viewport clamp off). Font-only
widget: the two callers resolve their faces from different modules, so they pass
them in (same rationale as the crosshair's colour policy) - no ``Theme`` needed.
"""
from __future__ import annotations

import pygame

__all__ = ["draw", "build"]


def draw(surface, sx, sy, text, col, *, font, y_off=-46, icon=None,
         fallback_font=None, fill=(8, 8, 12, 220), rim=None, radius=3,
         pad=(10, 5), clamp=True, max_label_w=None):
    """Draw a prompt tag centred on ``(sx, sy)``, ``y_off`` px above it.

    ``icon`` is an already-resolved surface (the caller owns the art pack); it
    is drawn in M3's icon slot (18x18 at the left inset). ``fallback_font`` plus
    the shrink guard keep a long string inside the viewport (M3's guarantee);
    ``clamp=False`` keeps the tag where it was asked to be (M5's behaviour).
    """
    for img, pos in build(surface.get_size(), sx, sy, text, col, font=font, y_off=y_off, icon=icon,
                          fallback_font=fallback_font, fill=fill, rim=rim, radius=radius, pad=pad, clamp=clamp,
                          max_label_w=max_label_w):
        surface.blit(img, pos)


def build(size, sx, sy, text, col, *, font, y_off=-46, icon=None,
          fallback_font=None, fill=(8, 8, 12, 220), rim=None, radius=3,
          pad=(10, 5), clamp=True, max_label_w=None):
    """The tag as ``[(surface, topleft), ...]`` in screen space (plate, icon, label) for the
    RPE6 render queue; ``size`` is the viewport size ``draw`` would have read from its target."""
    sw, sh = size
    pad_x, pad_y = pad
    label = font.render(text, True, col)
    if max_label_w is None:
        max_label_w = sw - 32 - pad_x * 2
    # Long localized/objective strings used to create plates wider than the
    # viewport. Prefer the small terminal face, then scale as a final guard.
    if fallback_font is not None and label.get_width() > max_label_w:
        label = fallback_font.render(text, True, col)
    if label.get_width() > max_label_w:
        scale = max_label_w / max(1, label.get_width())
        label = pygame.transform.smoothscale(
            label, (max_label_w, max(1, int(label.get_height() * scale))))
    ic = icon
    if ic is not None:
        ic = pygame.transform.smoothscale(ic, (18, 18))
    w = min(sw - 12,
            label.get_width() + pad_x * 2 + (22 if ic else 0))
    h = label.get_height() + pad_y * 2
    x = int(sx - w // 2)
    y = int(sy + y_off)
    if clamp:
        x = max(6, min(sw - w - 6, x))
        y = max(52, min(sh - h - 70, y))
    plate = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(plate, fill, plate.get_rect(), border_radius=radius)
    pygame.draw.rect(plate, rim if rim is not None else (*col[:3], 220),
                     plate.get_rect(), 1, border_radius=radius)
    out = [(plate, (x, y))]
    if ic is not None:
        out.append((ic, (x + 4, y + pad_y)))
        out.append((label, (x + pad_x + 22, y + pad_y)))
    else:
        out.append((label, (x + pad_x, y + pad_y)))
    return out
