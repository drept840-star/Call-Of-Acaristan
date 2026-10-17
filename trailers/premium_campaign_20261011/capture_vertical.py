"""Native portrait viewport capture. Changes display dimensions ONLY inside this process.
No production edits; native game renderer/collisions/weapons/AI. 540x960 -> 1080x1920 at integer 2x.
Existing checkpoint staging; HP/ammo untouched. Saves/settings sandboxed by imported capture harness.
"""
import sys,os,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
os.chdir(ROOT); sys.path.insert(0,str(ROOT/'tools'))
protected={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['save_data.json','settings.json','profile.json'] if Path(p).exists()}
import record_fresh_action as r
# Load mission modules before rebinding copied viewport constants. Never change map dimensions.
acts=r._act_table()
old=r.config.screen
new=r.pygame.display.set_mode((540,960))
for mod in list(sys.modules.values()):
 if mod is None: continue
 ns=vars(mod)
 if ns.get('WIDTH')==1000: ns['WIDTH']=540
 if ns.get('HEIGHT')==700: ns['HEIGHT']=960
 if ns.get('screen') is old: ns['screen']=new
r.Driver._invulnerable=lambda self:None
r.apply_hud_policy('clean'); r.SETTINGS.show_crosshair=False
orig=r.Driver.tick; traces=[]
def tick(self):
 orig(self)
 p=r.STATE.player
 if p: traces.append(dict(t=self.tickno/60,player=[p.rect.centerx-self.cam[0],p.rect.centery-self.cam[1]],hp=p.hp,dead=r.STATE.player_dead,enemies=[[e.rect.centerx-self.cam[0],e.rect.centery-self.cam[1],getattr(e,'hp',0)] for e in r.STATE.enemies]))
r.Driver.tick=tick
reports=[]
for act in acts:
 act=dict(act); act['key']='vertical'+str(act['n']); traces.clear()
 args=type('Args',(),dict(seed=20261011,seconds=12,out_dir=str(OUT),crosshair=False,no_ghost_filter=True))()
 rep,err,total,driver=r.capture_act(act,args,r.ffmpeg_exe()); rep['error']=err
 (OUT/(act['key']+'.trace.json')).write_text(json.dumps(traces)); reports.append(rep)
 print(json.dumps({k:rep[k] for k in ['act','shots','kills','seconds','error']}),flush=True)
 r.interactions.clear_radio_queue()
unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in protected.items())
(OUT/'vertical_report.json').write_text(json.dumps(dict(acts=reports,protected_unchanged=unchanged,native_viewport=[540,960],hp_ammo_refill=False),indent=2))
print('PROTECTED_UNCHANGED',unchanged)
