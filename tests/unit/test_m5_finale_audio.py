"""Focused M5 sound/lifecycle regressions, without starting app or saves.
Run: python -m unittest tests.unit.test_m5_finale_audio -v
"""
import ast
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from missions.m5.finale_audio import (FinaleAudio, GENERATORS, STEMS, FOLEY, RATE,
                                      stem_pcm, foley_pcm, _wav, _duck)
from missions.m5.finale_script import FINAL_SHOT, CUES, DURATION_MS, LINES


class Channel:
    def __init__(self, sound):
        self.sound=sound; self.busy=True; self.paused=False; self.stops=0; self.volume=1
    def get_busy(self): return self.busy
    def get_sound(self): return self.sound
    def pause(self): self.paused=True
    def unpause(self): self.paused=False
    def stop(self): self.busy=False; self.stops+=1
    def set_volume(self, v): self.volume=v


class Sound:
    def __init__(self): self.channels=[]
    def set_volume(self, v): self.volume=v
    def play(self):
        c=Channel(self); self.channels.append(c); return c


class Manager:
    master_volume=.8; sfx_volume=1.; _current_music_vol=.5
    def __init__(self): self.sounds={n:Sound() for n in STEMS+FOLEY}; self.calls=[]
    def register_lazy_generators(self,gens):   # AudioManager API (finale owns its set)
        for name,gen in gens:
            self.sounds.setdefault(name,Sound())
    def get_sound(self,n): return self.sounds.get(n)
    def play(self,n,volume=1):
        self.calls.append((n,volume));return self.get_sound(n).play()
    def stop(self,n): pass


def player_harness():
    clock=[0]; routes=[]; amb=[]; manager=Manager()
    voice=SimpleNamespace(stop=lambda:None,pause=lambda:None,resume=lambda:None)
    pygame=SimpleNamespace(KEYDOWN=1,K_ESCAPE=27,K_RETURN=13,K_SPACE=32,
        time=SimpleNamespace(get_ticks=lambda:clock[0]),
        event=SimpleNamespace(Event=lambda type,**kw:SimpleNamespace(type=type,**kw)),
        mouse=SimpleNamespace(set_visible=lambda v:None))
    ns=dict(pygame=pygame,GameState=object,audio=manager,voice=voice,
        _now_ms=lambda:clock[0],
        KO_CUT_CUES={},TEXT_SPEED=4,gc=SimpleNamespace(reset_dialogue_slide=lambda:None),
        gsm=SimpleNamespace(transition=routes.append),_set_ambience=amb.append,
        _play_typewriter_tick=lambda *a,**kw:None,
        mission_complete_timer=0,mission_complete_fade=0)
    tree=ast.parse((ROOT/'src/app.py').read_text(encoding='utf-8-sig'))
    nodes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name in ('CutscenePlayer','_CutsceneState')]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'production_player','exec'),ns)
    cp=ns['CutscenePlayer']([FINAL_SHOT],'MISSION5_COMPLETE');ns['active_cutscene']=cp
    cp.finale_audio=FinaleAudio(manager)
    return cp,ns['_CutsceneState'](),clock,routes,amb,manager


class SoundDesignTests(unittest.TestCase):
    def test_all_cues_are_registered_and_within_film(self):
        names={n for n,_ in GENERATORS}
        self.assertEqual({n for _,n,_ in CUES},set(FOLEY))
        self.assertTrue(set(FOLEY+STEMS)<=names)
        self.assertTrue(all(0<=ms<DURATION_MS and 0<vol<=1 for ms,_,vol in CUES))
        self.assertEqual(list(CUES),sorted(CUES,key=lambda c:c[0]))
        self.assertNotIn('radio_static',{n for _,n,_ in CUES})
        self.assertFalse(any('gunshot' in n for _,n,_ in CUES))

    def test_stems_are_stereo_bounded_and_fade_to_silence(self):
        for name in STEMS:
            x=stem_pcm(name)
            self.assertEqual(x.shape,(round(RATE*DURATION_MS/1000),2))
            self.assertTrue(np.isfinite(x).all())
            self.assertLess(np.abs(x).max(),.3)
            self.assertGreater(np.sqrt(np.mean(x*x)),.003)
            self.assertTrue(np.all(x[0]==0) and np.all(x[-1]==0))
            self.assertGreater(np.sqrt(np.mean((x[:,0]-x[:,1])**2)),.001)
            with wave.open(io.BytesIO(_wav(x)),'rb') as w:
                self.assertEqual((w.getnchannels(),w.getsampwidth(),w.getframerate()),(2,2,RATE))
                self.assertEqual(w.getnframes(),len(x))

    def test_foley_is_repeatable_and_no_hard_end(self):
        for name in FOLEY:
            a=foley_pcm(name);b=foley_pcm(name)
            self.assertTrue(np.array_equal(a,b))
            self.assertLess(np.abs(a).max(),.85)
            self.assertTrue(np.all(a[0]==0) and np.all(a[-1]==0))

    def test_finale_reuses_game_audio_palette_without_advancing_rng(self):
        from audio import audio as shared
        before = shared._rng_legacy.getstate()
        stem_pcm.cache_clear()
        with patch.object(shared, '_gen_rain', wraps=shared._gen_rain) as rain, \
             patch.object(shared, '_gen_wind', wraps=shared._gen_wind) as wind, \
             patch.object(shared, '_gen_ambient_drone', wraps=shared._gen_ambient_drone) as drone, \
             patch.object(shared, '_gen_footstep_wet', wraps=shared._gen_footstep_wet) as step:
            for name in STEMS:
                stem_pcm(name)
            foley_pcm('m5_wet_step')
            self.assertTrue(rain.called, 'Finale must use the shared filtered rain')
            self.assertTrue(wind.called, 'Finale must use the shared wind')
            self.assertTrue(drone.called, 'Finale must use the established drone, not a new chord')
            self.assertTrue(step.called, 'Finale footsteps must use the gameplay wet-step palette')
        self.assertEqual(shared._rng_legacy.getstate(), before)

    def test_voice_windows_duck_without_missing_take_dependency(self):
        for on,off,*_ in LINES:
            self.assertAlmostEqual(_duck(np.array([(on+off)/2000]))[0],.44)
        self.assertEqual(_duck(np.array([1.]))[0],1.)


class OwnershipTests(unittest.TestCase):
    def test_start_once_and_live_volume_sliders(self):
        m=Manager();a=FinaleAudio(m);a.prepare();a.update(0);a.update(16)
        self.assertEqual([len(m.sounds[n].channels) for n in STEMS],[1,1])
        self.assertEqual(a.channels[STEMS[0]].volume,.8)
        self.assertEqual(a.channels[STEMS[1]].volume,.4)
        m.sfx_volume=.2;m._current_music_vol=0;a.update(32)
        self.assertAlmostEqual(a.channels[STEMS[0]].volume,.16)
        self.assertEqual(a.channels[STEMS[1]].volume,0)

    def test_pause_resume_and_idempotent_stop(self):
        a=FinaleAudio(Manager());a.update(0)
        c=Channel(Sound());a.track(c);ch=list(a.channels.values())+[c]
        a.pause();self.assertTrue(all(x.paused for x in ch))
        a.update(9000);self.assertEqual(a.last_ms,0)
        a.resume();self.assertFalse(any(x.paused for x in ch))
        a.stop();a.stop();self.assertTrue(all(x.stops==1 for x in ch))
        a.update(0);self.assertFalse(a.channels)

    def test_reused_foley_channel_is_not_paused_or_stopped(self):
        a=FinaleAudio(Manager());c=Channel(Sound());a.track(c)
        c.sound=Sound()  # Mixer reused it for an unrelated gameplay sound.
        a.pause();a.resume();a.stop()
        self.assertFalse(c.paused);self.assertEqual(c.stops,0)

    def test_no_audio_device_still_reaches_end(self):
        m=Manager();m.sounds={};a=FinaleAudio(m);a.prepare();a.update(0)
        a.update(DURATION_MS);self.assertTrue(a.closed)

    def test_jump_seeks_stems_instead_of_replaying_opening(self):
        m=Manager();a=FinaleAudio(m);a.update(0);old=list(a.channels.values())
        tails=[]
        def load(buf):
            with wave.open(buf,'rb') as w: tails.append(w.getnframes())
            return Sound()
        with patch('pygame.mixer.Sound',side_effect=load):a.update(20000)
        self.assertTrue(all(c.stops==1 for c in old))
        self.assertEqual(tails,[22*RATE,22*RATE])

    def test_real_mixer_play_pause_seek_and_stop(self):
        import pygame
        pygame.mixer.init(frequency=RATE,size=-16,channels=2)
        m=Manager()
        m.sounds={n:pygame.mixer.Sound(io.BytesIO(gen())) for n,gen in GENERATORS}
        a=FinaleAudio(m);a.prepare();a.update(0)
        self.assertEqual(len(a.channels),2)
        channels=list(a.channels.values())
        a.track(m.play(FOLEY[0]));a.pause();a.resume();a.update(20000)
        self.assertEqual(len(a.seek_sounds),2)
        self.assertTrue(all(c.get_busy() for c in a.channels.values()))
        a.stop()
        self.assertFalse(any(c.get_busy() for c in channels))
        pygame.mixer.stop()

    def test_production_pause_cancel_skip_and_exit(self):
        cp,state,clock,routes,amb,m=player_harness();state.enter();state.update(1/60)
        old=list(cp.finale_audio.channels.values())
        event=lambda k:SimpleNamespace(type=1,key=k)
        state.handle_event(event(27),0,0,{})
        self.assertTrue(cp.paused and all(c.paused for c in old))
        clock[0]=4000;state.update(1/60);self.assertEqual(cp.elapsed_ms,0)
        state.handle_event(event(27),0,0,{})
        self.assertFalse(cp.paused or any(c.paused for c in old))
        state.set_ambience();self.assertEqual(amb[-1],set())
        state.handle_event(event(13),0,0,{});state.handle_event(event(27),0,0,{})
        self.assertFalse(cp.skip_confirm);self.assertFalse(cp.finale_audio.closed)
        state.handle_event(event(13),0,0,{});state.handle_event(event(13),0,0,{})
        state._handle_end();state.exit()
        self.assertEqual(routes,['MISSION_COMPLETE']);self.assertTrue(cp.finale_audio.closed)
        self.assertTrue(all(c.stops==1 for c in old))

    def test_production_normal_completion_at_different_update_rates(self):
        for step in (16,33,100):
            cp,state,clock,routes,amb,m=player_harness();state.enter()
            with patch('audio.voice.play_line',return_value=0):
                for elapsed in range(0,DURATION_MS,step):
                    clock[0]=elapsed;state.update(step/1000)
                clock[0]=DURATION_MS;state.update(step/1000)
            self.assertEqual(routes,['MISSION_COMPLETE'])
            self.assertTrue(cp.finale_audio.closed)
            names=[n for n,_ in m.calls]
            # The finale owns its ticking too (one type_tick per revealed glyph at
            # 50 ms/char, tracked by finale_audio._tick_lines); everything else is
            # the authored CUES exactly once, in order.
            self.assertEqual([n for n in names if n!='type_tick'],
                             [n for _,n,_ in CUES])
            self.assertGreater(names.count('type_tick'),0)

    def test_production_long_jump_discards_missed_foley(self):
        cp,state,clock,routes,amb,m=player_harness();clock[0]=20000
        with patch('pygame.mixer.Sound',return_value=Sound()),patch('audio.voice.play_line',return_value=0):
            state.update(1/60);state.update(1/60)
        self.assertEqual(m.calls,[])


if __name__=='__main__': unittest.main()
