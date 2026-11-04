"""Pause/resume for the mixer without the alt-tab deadlock.

pygame-ce 2.5's mixer.pause(), music.pause(), music.unpause() and
Channel.pause()/unpause() take SDL's audio lock while still holding the GIL.
The audio thread's channel-finished callback (endsound_callback) runs with
that lock held and then asks for the GIL. A sound ending during one of those
calls deadlocks the game: the window stops responding and never comes back
(seen on alt-tab mute and in the pause menu). ctypes releases the GIL for the
foreign call, so these go straight to the SDL2_mixer.dll pygame already
loaded. If the DLL can't be found, they fall back to the pygame calls.
"""
import ctypes
import os

import pygame

_dll = None
try:
    _path = os.path.join(os.path.dirname(pygame.__file__), "SDL2_mixer.dll")
    if os.path.exists(_path):
        _dll = ctypes.CDLL(_path)
        _dll.Mix_Pause.argtypes = [ctypes.c_int]
        _dll.Mix_Resume.argtypes = [ctypes.c_int]
except Exception:
    _dll = None


def _ready():
    return _dll is not None and pygame.mixer.get_init()


def pause(channel=-1):
    """Pause one channel (by id) or every channel (-1)."""
    if _ready():
        _dll.Mix_Pause(channel)
    elif channel < 0:
        pygame.mixer.pause()
    else:
        pygame.mixer.Channel(channel).pause()


def resume(channel=-1):
    """Resume one channel (by id) or every channel (-1)."""
    if _ready():
        _dll.Mix_Resume(channel)
    elif channel < 0:
        pygame.mixer.unpause()
    else:
        pygame.mixer.Channel(channel).unpause()


def pause_music():
    if _ready():
        _dll.Mix_PauseMusic()
    else:
        pygame.mixer.music.pause()


def resume_music():
    if _ready():
        _dll.Mix_ResumeMusic()
    else:
        pygame.mixer.music.unpause()
