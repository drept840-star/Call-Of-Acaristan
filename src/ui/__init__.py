
"""Package ui - re-export facade. Parts: widgets.py, main.py, mp.py, system.py."""
from .widgets import *  # noqa: F401,F403
from .main import *  # noqa: F401,F403
from .mp import *  # noqa: F401,F403
from .system import *  # noqa: F401,F403
from .radio import RadioTransmission, TRANSMISSION, draw_radio, recent_lines  # noqa: F401
from .widgets import _menu_overlay, _btn_hover_bg, _subtitle_font, _tagline_font, _footer_font, _classification_font, _micro_font, _glyph_font, _lerp_dt  # noqa: F401
from .main import _MenuAnimState, _anim, _BOOT_LINES, _BOOT_LINE_DELAY, _BOOT_CHAR_RATE, _TICKER_ITEMS, _TICKER_SPEED, _init_menu_anim, _update_menu_anim, _draw_rain, _draw_embers, _draw_vignette, _draw_title_glow, _draw_scanline_drift, _draw_boot_banner, _draw_news_ticker, _visible_button_indices  # noqa: F401
from .mp import _dm_open_user, _dm_history, _dm_input, _dm_response_delay, _dm_pending_reply, _dm_scroll_offset, _mp_tab, _chat_messages, _chat_next_spawn, _server_animation_timer, _refresh_active, _refresh_progress, _scroll_offset, _server_status, _draw_server_badge, _fit_text, _status_color, _server_shade, _server_panel, _wrap_server_name  # noqa: F401
from .system import _VOL_GRADIENT, _CRT_SCANLINES, _settings_overlay, _settings_panel, _draw_arrow_btn, _draw_volume_slider, _draw_toggle, _draw_stepper, _draw_section_header, _draw_hint, _pause_overlay, _pause_panel_x, _pause_panel_y, _pause_panel_frame, _banner_y, _banner_font, _banner_text, _title_y, _title_shadow, _title_main, _bar_y, _footer_font, _footer_text, _pause_stat_label_font, _pause_stat_value_font, _format_elapsed, _death_animation_start, _death_particles, _death_font, _death_sub_font, _death_flavor_font, _server_title_font, _black_ledger_death_button_progress, _pause_panel_h, _pause_panel_w  # noqa: F401

del _dm_open_user, _dm_history, _dm_input, _dm_response_delay, _dm_pending_reply, _dm_scroll_offset, _mp_tab, _chat_messages, _chat_next_spawn, _server_animation_timer, _refresh_active, _refresh_progress, _scroll_offset, _server_shade, _server_panel, _VOL_GRADIENT, _CRT_SCANLINES, _settings_overlay, _settings_panel, _pause_overlay, _pause_panel_x, _pause_panel_y, _pause_panel_frame, _banner_y, _banner_font, _banner_text, _title_y, _title_shadow, _title_main, _bar_y, _footer_font, _footer_text, _pause_stat_label_font, _pause_stat_value_font, _death_animation_start, _death_particles, _death_font, _death_sub_font, _death_flavor_font, _server_title_font, _black_ledger_death_button_progress, _pause_panel_h, _pause_panel_w


_LIVE_STATE = frozenset([
    "_dm_open_user",
    "_dm_history",
    "_dm_input",
    "_dm_response_delay",
    "_dm_pending_reply",
    "_dm_scroll_offset",
    "_mp_tab",
    "_chat_messages",
    "_chat_next_spawn",
    "_chat_input",
    "_connect_input",
    "_connect_focused",
    "_connect_msg",
    "_connect_msg_age",
    "_connect_rect",
    "_connect_btn_rect",
    "_server_animation_timer",
    "_refresh_active",
    "_refresh_progress",
    "_scroll_offset",
    "_relay_status",
    "_relay_error",
    "_relay_client",
    "_relay_rules",
    "_relay_host",
    "_relay_port",
    "_server_shade",
    "_server_panel",
    "_VOL_GRADIENT",
    "_CRT_SCANLINES",
    "_settings_overlay",
    "_settings_panel",
    "_pause_overlay",
    "_pause_panel_x",
    "_pause_panel_y",
    "_pause_panel_frame",
    "_banner_y",
    "_banner_font",
    "_banner_text",
    "_title_y",
    "_title_shadow",
    "_title_main",
    "_bar_y",
    "_footer_font",
    "_footer_text",
    "_pause_stat_label_font",
    "_pause_stat_value_font",
    "_death_animation_start",
    "_death_particles",
    "_death_font",
    "_death_sub_font",
    "_death_flavor_font",
    "_server_title_font",
    "_black_ledger_death_button_progress",
    "_pause_panel_h",
    "_pause_panel_w",
])

_LIVE_MODULES = (
    "ui.system",
    "ui.mp",
    "ui.main",
    "ui.widgets",
)


def __getattr__(name):
    """PEP 562 live view for rebound shared state (see _LIVE_STATE)."""
    if name in _LIVE_STATE:
        import sys as _sys2
        for _mod in _LIVE_MODULES:
            _m = _sys2.modules.get(_mod)
            if _m is not None and name in vars(_m):
                return vars(_m)[name]
    raise AttributeError(
        "module " + repr(__name__) + " has no attribute " + repr(name))
