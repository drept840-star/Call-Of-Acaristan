"""entities.sprite_lib - deprecated path (RPE6 Phase 2, A-006): see ``engine.assets.sprites``."""
import warnings as _warnings

from engine.assets import sprites as _impl
from core.config import resource_path as _resource_path

_warnings.warn("entities.sprite_lib moved to engine.assets.sprites (RPE6 A-006)", DeprecationWarning, stacklevel=2)
_impl.configure(_resource_path)

sprite_path = _impl.sprite_path
get_sprite = _impl.get_sprite
