# Replace the body of _m3_draw_balaceanu in src/cutscenes/m3cell.py with this.
def _m3_draw_balaceanu(surface, cx, foot_y, scale=1.0, facing_left=True):
    """Balaceanu, drawn by figure_kit so he matches the arrest scene exactly
    (same face/suit as m4aftermath's general), holding the VOSTRAL folder."""
    from .figure_kit import draw_character
    draw_character(surface, "balaceanu", cx, foot_y, scale, facing_right=not facing_left,
                   prop="folder", prop_label="VOSTRAL", label_font=font_terminal_small)
