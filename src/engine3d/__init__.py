"""engine3d - tiny flat-shaded low-poly software renderer for pygame.

Two backends share one API: ``SoftwareRenderer`` (no GPU) and ``GLRenderer``
(ModernGL, see gl.py). ``Renderer(...)`` picks GL when available.
The software path: meshes are transformed in Python and painted with
pygame.draw.polygon back-to-front (painter's algorithm) into a low-res
buffer that is upscaled with nearest-neighbour for a chunky PS1 look.

    from engine3d import Renderer, Mesh, box, prism
"""
from .core import *  # noqa: F401,F403
from .rig import *   # noqa: F401,F403
from .gl import GLRenderer, Renderer, gl_available, gl_info  # noqa: F401  (GPU backend, auto-fallback)
