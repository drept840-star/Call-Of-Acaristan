"""Focused check for retiring the M5 finale without losing campaign completion.

python tools/m5_finale_cut_check.py
Runs actual mission and app state classes without launching the app/game loop.
Writes completion records ONLY to a temporary test store.
"""
import ast
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
from engine.core import now_ms as _now_ms,pin_wall as _pin_wall,unpin_wall as _unpin_wall  # RPE6 B-001


def check():
    import pygame
    from core import game_core as gc,save_system
    from core.state import STATE
    from core.fsm import GameState,GameStateManager
    from missions.m5 import flow,meta
    original_shots = list(meta.mission5_ending_shots)
    meta.mission5_ending_shots.clear()
    assert meta.mission5_ending_shots==[]
    assert gc.mission5_ending_shots is meta.mission5_ending_shots
    assert meta.mission5_intro_shots and meta.M5_MID_CUTSCENES
    assert not any(p['name']=='The Standoff' for p in meta.MISSION_PHASES)
    before=vars(STATE).copy();old_save=save_system.SAVE_FILE
    tick=pygame.time.get_ticks
    try:
        with tempfile.TemporaryDirectory(prefix='m5_finale_cut_') as tmp:
            save_system.SAVE_FILE=str(Path(tmp)/'save.json')
            save_system.select_slot(1);save_system.start_new_campaign(1)
            gc.start_mission5_tunnel_checkpoint()
            # Production gate: Biribel alone does not complete the escort.
            class Keys:
                def __getitem__(self,key):return False
            gate=flow._river_gate_pos()
            STATE.player.rect.center=gate
            STATE.m5_maru['x']=gate[0]-300;STATE.m5_maru['y']=gate[1]
            STATE.m5_maru['hp']=120;STATE.m5_squad_timer=999
            old_maru=flow._update_maru
            flow._update_maru=lambda:None
            try:
                flow._update_stage(Keys())
                assert not STATE.request_mission5_ending,'Biribel skipped the Maru escort'
                STATE.m5_maru['x'],STATE.m5_maru['y']=gate
                pygame.time.get_ticks=lambda:123456;_pin_wall(ms=123456)
                flow._update_stage(Keys())
                assert STATE.request_mission5_ending and STATE.mission5_stage==meta.STAGE_DONE
                assert STATE.mission_end_time==123456
            finally:flow._update_maru=old_maru
            # Execute the real app classes, with only external boundaries mocked.
            tree=ast.parse((ROOT/'src/app.py').read_text(encoding='utf-8-sig'))
            classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name in ('_GameState_','_MissionCompleteState')]
            # Block the optional trailer bot while still exercising full update().
            inactive=SimpleNamespace(is_active=lambda:False)
            previous=sys.modules.get('tools.trailer_bot')
            sys.modules['tools.trailer_bot']=inactive
            saves=[];radio=[];cuts=[];fades=[]
            def save(*args,**kw):
                saves.append(args[0]);return save_system.save_mission_complete_record(*args,**kw)
            stubgc=SimpleNamespace(active_mission='MISSION5',request_death_screen=False,
                request_notebook_inspect=False,request_mission5_ending=True,
                mission5_ending_shots=meta.mission5_ending_shots,game_update=lambda keys:(0,0))
            manager=GameStateManager()
            env={'GameState':GameState,'pygame':pygame,'gc':stubgc,'STATE':STATE,'gsm':manager,'_now_ms':_now_ms,
                 'keys':Keys(),'_input_recorder':SimpleNamespace(enabled=lambda:False),
                 'interactions':SimpleNamespace(clear_radio_queue=lambda:radio.append(True)),
                 'start_cutscene':lambda *a,**k:cuts.append(a),'trigger_transition':fades.append,
                 '_m5_mid_cut_key':lambda:None,'mission_complete_timer':777,'mission_complete_fade':255,
                 '_mission_report_data':lambda success:{'time_str':'02:03','rank':'A','score':85},
                 'save_system':SimpleNamespace(save_mission_complete_record=save),
                 '_apply_equipped_look':lambda:None,'_set_ambience':lambda sounds:None}
            try:
                exec(compile(ast.Module(body=classes,type_ignores=[]),str(ROOT/'src/app.py'),'exec'),env)
                game=env['_GameState_']();complete=env['_MissionCompleteState']()
                manager.add(game);manager.add(complete);manager.transition('GAME')
                game.update(1/60)
                assert manager.current_name=='MISSION_COMPLETE'
                assert not cuts and not fades,'Cut finale entered CUTSCENE/fade'
                assert not stubgc.request_mission5_ending
                assert radio==[True] and saves==['MISSION5']
                assert env['mission_complete_timer']==env['mission_complete_fade']==0
                slot=save_system.get_slot(1)
                assert slot['last_completed_mission']=='MISSION_5'
                for flag in ('mission1_complete','mission2_complete','mission3_complete','mission4_complete','mission5_complete'):
                    assert slot['flags'][flag],flag
                # Consuming the request must not allow completion to relatch.
                STATE.request_mission5_ending=False
                pygame.time.get_ticks=lambda:999999;_pin_wall(ms=999999)
                flow._complete_m5()
                assert STATE.mission_end_time==123456 and not STATE.request_mission5_ending
                # Completion screen still leads to MENU on continue.
                complete.handle_event(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE),0,0,{})
                assert fades==['MENU']
                # Future nonempty finale still uses the existing cutscene route.
                stubgc.request_mission5_ending=True
                stubgc.mission5_ending_shots=[{'scene':'future_m5_finale'}]
                cuts.clear();fades.clear()
                game.update(1/60)
                assert len(cuts)==1 and fades==['CUTSCENE']
            finally:
                if previous is None:sys.modules.pop('tools.trailer_bot',None)
                else:sys.modules['tools.trailer_bot']=previous
    finally:
        meta.mission5_ending_shots[:] = original_shots
        pygame.time.get_ticks=tick;_unpin_wall()
        save_system.SAVE_FILE=old_save
        vars(STATE).clear();vars(STATE).update(before)
    print('M5 EMPTY-FINALE FALLBACK: OK (escort gate, direct completion, save record, no replay, MENU continue)')


if __name__=='__main__':
    check()
