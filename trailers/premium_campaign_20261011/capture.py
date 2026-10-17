"""Isolated fresh capture using existing mission input/checkpoint paths.
No game source changes, no HP/ammo refills, no bare mirror mask. Saves sandboxed by original harness.
Run from repository root: python trailers/premium_campaign_20261011/capture.py
"""
import sys,os,json,random,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
os.chdir(ROOT); sys.path.insert(0,str(ROOT/'tools'))
protected=['save_data.json','settings.json','profile.json']
before={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in protected if Path(p).exists()}
import record_fresh_action as r
r.Driver._invulnerable=lambda self: None
acts=r._act_table(); r.apply_hud_policy('clean'); r.SETTINGS.show_crosshair=False
orig=r.Driver.tick
traces=[]
def tick(self):
 orig(self)
 p=r.STATE.player
 if p:
  traces.append(dict(t=self.tickno/60,player=[p.rect.centerx-self.cam[0],p.rect.centery-self.cam[1]],hp=p.hp,weapon=getattr(r.STATE,'current_weapon',''),enemies=[[e.rect.centerx-self.cam[0],e.rect.centery-self.cam[1],getattr(e,'hp',0)] for e in r.STATE.enemies],dead=r.STATE.player_dead))
r.Driver.tick=tick
args=type('Args',(),dict(seed=20261011,seconds=12,out_dir=str(OUT),crosshair=False,no_ghost_filter=True))()
reports=[]
for act in acts:
 traces.clear(); rep,err,total,driver=r.capture_act(act,args,r.ffmpeg_exe())
 (OUT/f"act{act['n']}.trace.json").write_text(json.dumps(traces))
 rep['error']=err; rep['truthful_capture']='No invulnerability or ammunition refill'; reports.append(rep)
 print(json.dumps({k:rep[k] for k in ['act','shots','kills','seconds','error']}),flush=True)
 r.interactions.clear_radio_queue()
# Implemented cinematic scene dispatch. Render native game frames, no added narrative scenes.
from cutscenes.engine import draw_cutscene_scene
for scene in ['monitor_broadcast','cb_crack','k9_firstperson_grab','van_handoff','route12_checkpoint']:
 p=OUT/(scene+'.mp4')
 proc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1000x700','-r','30','-i','-','-an','-c:v','libx264','-crf','14','-pix_fmt','yuv420p',str(p)],stdin=subprocess.PIPE)
 for n in range(90):
  draw_cutscene_scene(r.config.screen,{'scene':scene},n*1000/30)
  proc.stdin.write(r.pygame.image.tobytes(r.config.screen,'RGB'))
 proc.stdin.close(); proc.wait(); print('CINEMATIC',scene,proc.returncode,flush=True)
after={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in before}
(OUT/'capture_report.json').write_text(json.dumps(dict(acts=reports,protected_unchanged=before==after,before=before,after=after),indent=2))
print('PROTECTED_UNCHANGED',before==after)
