"""engine.core: kernel services (clock, rng, events, log, config, services, errors, app).

Depends only on the stdlib (and pygame inside App.boot / crash screenshots).
"""
from .app import App
from .clock import DEFAULT_HZ, DEFAULT_MAX_STEPS, Clock
from .config import DEFAULTS, ENV_MAP, Settings
from .errors import AEError, AssetError, SchemaError, TimelineError, write_crash_report
from .events import EventBus, Subscription
from .log import CHANNELS, LEVELS, Log, get_log
from .mathx import clamp, ease_in_out_cubic, ease_out_quad, inv_lerp, lerp, lerp_angle, smoothstep
from .profiling import Profiler
from .rng import LEGACY, LEGACY_RNG, RngStreams, derive_seed
from .services import ServiceMissing, Services
from .timebase import now_ms, now_s, pin_wall, unpin_wall

__all__ = [
    "AEError", "App", "AssetError", "CHANNELS", "Clock", "DEFAULTS", "DEFAULT_HZ", "DEFAULT_MAX_STEPS",
    "ENV_MAP", "EventBus", "LEGACY", "LEGACY_RNG", "LEVELS", "Log", "Profiler", "RngStreams", "SchemaError", "ServiceMissing",
    "Services", "Settings", "Subscription", "TimelineError", "clamp", "derive_seed", "ease_in_out_cubic",
    "ease_out_quad", "get_log", "inv_lerp", "lerp", "lerp_angle", "now_ms", "now_s", "pin_wall", "smoothstep",
    "unpin_wall", "write_crash_report",
]
