"""Reproducible campaign short. Run from repo root; requires ffmpeg, numpy, Pillow.
python trailers/premium_campaign_20261011/assemble.py --revision 1
python trailers/premium_campaign_20261011/assemble.py --revision 2
Fresh native portrait gameplay; source-rendered cinematics. No invented visual events.
"""
import os,sys,json,io,wave,subprocess,random,argparse
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
os.chdir(ROOT); os.environ['SDL_AUDIODRIVER']='dummy';os.environ['SDL_VIDEODRIVER']='dummy'
FPS=30; SR=48000; W,H=1080,1920
FONT=ROOT/'assets/fonts/Oswald.ttf'; BONE=(239,231,211); ORANGE=(255,120,0); DARK=(10,16,21)
def font(n):return ImageFont.truetype(str(FONT),n)
LOGO=Image.open(ROOT/'wordmark.png').convert('RGBA')
# If asset has solid margins they remain part of the actual wordmark.
LOGO.thumbnail((810,305),Image.Resampling.LANCZOS)
def text(im,line,y,size=66,color=BONE):
 d=ImageDraw.Draw(im); f=font(size); box=d.textbbox((0,0),line,font=f); x=110
 if box[2]>810: raise ValueError('copy outside conservative safe area: '+line)
 d.text((x,y),line,font=f,fill=color,stroke_width=2,stroke_fill=DARK)
def command(args):
 r=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-2500:])
 return r

def make_shots(rev,hook='sniper'):
 # A retained 6.8-second fight: setup -> movement/fire -> enemy impact -> next wave.
 shots=[dict(src='vertical2',start=.4,duration=2,kind='game',text='',why='Immediate sniper-acquisition warning and live fire'),
 dict(src='vertical1',start=3.7,duration=4.2,kind='game',text='Recover the notebook.',why='Warehouse movement, aim, enemy response'),
 dict(src='monitor_broadcast',start=.3,duration=2,kind='monitor',text="Now you are the story.",why='Actual state accusation on monitor, no late-game reveal'),
 dict(src='cb_crack',start=.7,duration=2,kind='cinema',crop=[350,80,330,540],text='Break their hold.',why='Implemented restraint-breaking cinematic'),
 dict(src='k9_firstperson_grab',start=1,duration=1.5,kind='cinema',crop=[310,80,380,540],text='',why='Existing first-person weapon retrieval'),
 dict(src='vertical3',start=.6,duration=3.6,kind='game',text='',why='Archives first contact and response'),
 dict(src='vertical3',start=9,duration=2.4,kind='game',text='',why='Archives approach and close fight'),
 dict(src='vertical2',start=4.6,duration=6.8,kind='game',text='Route 12 does not stay quiet.',why='Sustained firefight with real reload/impacts, hero sequence'),
 dict(src='vertical1',start=8.2,duration=2.3,kind='game',text='',why='Return to warehouse combat, thematic bookend'),
 dict(src='vertical2',start=9,duration=2.6,kind='end',text='',why='Real wordmark and truthful development-update CTA')]
 if hook=='breach':shots[0]=dict(src='cb_crack',start=.65,duration=2,kind='cinema',crop=[350,80,330,540],text='',why='Alternative: visible restraint rupture, not a combat breach')
 if hook=='warehouse':shots[0]=dict(src='vertical1',start=7.1,duration=2,kind='game',text='',why='Alternative: immediate warehouse encounter')
 if rev==2:
  # Revision after export inspection: retain readable break action wider, reduce scenic gun rack hold,
  # lengthen the archives contact so its approach/impact are no longer rushed.
  shots[3]['crop']=[260,80,480,540]
  shots[4]['duration']=1.0
  shots[5]['duration']=4.1
  shots[7]['text']='Fight through Route 12.'
 t=0
 for s in shots:s['timeline_in']=round(t,3);t+=s['duration'];s['timeline_out']=round(t,3)
 return shots

def decoder(s):
 p=OUT/(s['src']+'.mp4'); game=s['src'].startswith('vertical')
 vf='null' if game else 'null'
 proc=subprocess.Popen(['ffmpeg','-v','error','-ss',str(s['start']),'-i',str(p),'-frames:v',str(round(s['duration']*FPS)),'-vf',vf,'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 return proc,(540,960) if game else (1000,700)

def composition(im,s,branded,rev,local):
 if s['kind'] in ['game','end']:
  if rev==2 and s['kind']=='game' and s['timeline_in']>=2:
   if '_trace' not in s:s['_trace']=json.loads((OUT/(s['src']+'.trace.json')).read_text())
   trace=s['_trace'];rec=trace[min(len(trace)-1,max(0,round((s['start']+local)*60)))];px,py=rec['player']
   es=[e for e in rec['enemies'] if e[2]>0 and 0<e[0]<540 and 0<e[1]<960 and (e[0]-px)**2+(e[1]-py)**2<330**2]
   ex,ey=px,py
   if es:ex,ey,_=min(es,key=lambda e:(e[0]-px)**2+(e[1]-py)**2)
   desired=[max(0,min(180,(px+ex)/2-180)),max(0,min(320,(py+ey)/2-320))]
   if '_camera' not in s:s['_camera']=desired[:]
   for i in [0,1]:s['_camera'][i]+=max(-1,min(1,(desired[i]-s['_camera'][i])*.08))
   x,y=[round(v) for v in s['_camera']];im=im.crop((x,y,x+360,y+640))
   s.setdefault('reframe_path',[]).append([round(local,4),x,y])
  im=im.resize((W,H),Image.Resampling.NEAREST)
  # Single restrained tonal lift. No effects hide the renderer.
  lut=[min(255,round(255*(i/255)**.86)) for i in range(256)]
  im=im.point(lut*3)
 elif s['kind']=='monitor':
  # Deliberately composed context panel; preserves all accusation text instead of slicing it.
  plate=Image.new('RGB',(W,H),DARK)
  pic=im.crop((95,80 if rev==2 else 180,910,490 if rev==2 else 535));pic=pic.resize((960,round(pic.height*960/pic.width)),Image.Resampling.LANCZOS)
  plate.paste(pic,((W-pic.width)//2,645));im=plate
  if branded:
   text(im,'STATE ADDRESS',410,46,ORANGE)
   text(im,'22:00 / ACARISTAN',477,38)
 else:
  x,y,w,h=s['crop']; im=im.crop((x,y,x+w,y+h))
  # Cinema is not pixel-art gameplay. Aspect preserving cover-scale and gentle centre trim.
  k=max(W/w,H/h);im=im.resize((round(w*k),round(h*k)),Image.Resampling.LANCZOS)
  x=(im.width-W)//2;y=(im.height-H)//2; im=im.crop((x,y,x+W,y+H))
 if s['kind']=='end' and branded:
  # Quiet full-frame end plate, actual wordmark, no invented platform/date/link.
  shade=Image.new('RGBA',(W,H),(8,14,19,228)); im=Image.alpha_composite(im.convert('RGBA'),shade)
  im.alpha_composite(LOGO,(110,700));im=im.convert('RGB')
  text(im,'Follow for development updates.',1135,48)
  ImageDraw.Draw(im).line((110,1080,290,1080),fill=ORANGE,width=4)
 elif branded and s.get('text') and local>.12:
  y=(240 if rev==2 and s['kind']=='game' else 1270) if s['kind']!='monitor' else 1210
  text(im,s['text'],y,64 if rev==1 else 62)
 return im.convert('RGB')

def audio(shots,name):
 # Source-generated game SFX avoid unlicensed repository recordings; cue is newly composed here.
 sys.path.insert(0,str(ROOT/'src'))
 from audio import audio as a
 random.seed(61011); rng=np.random.default_rng(61011)
 total=shots[-1]['timeline_out']; N=round(total*SR); t=np.arange(N)/SR
 bed=np.zeros(N,dtype=np.float64); fx=np.zeros(N,dtype=np.float64)
 def add(dst,sig,when,gain=1):
  i=round(when*SR)
  if i<0:sig=sig[-i:];i=0
  n=min(len(sig),len(dst)-i)
  if n>0:dst[i:i+n]+=sig[:n]*gain
 def note(freq,dur,amp):
  u=np.arange(round(dur*SR))/SR
  sig=np.sin(2*np.pi*freq*u)+.24*np.sin(2*np.pi*freq*2*u)+.08*np.sin(2*np.pi*freq*5*u)
  env=np.minimum(u/.018,1)*np.exp(-u*3)*np.minimum((dur-u)/.06,1)
  return np.tanh(sig*1.4)*env*amp
 # Tension drone with audible midrange partials for phone playback.
 bed+=.036*(np.sin(2*np.pi*73.416*t)+.34*np.sin(2*np.pi*146.832*t))*(.72+.28*np.sin(2*np.pi*.17*t))
 beat=60/108
 for i,when in enumerate(np.arange(2,total-2.6,beat/2)):
  if 16.8<when<17.3:continue
  f=[146.832,146.832,174.614,155.563,146.832,130.813,110,130.813][i%8]
  gain=.052 if when<10 else (.079 if when<17 else .11)
  add(bed,note(f,.42,gain),when)
  if i%2==0 and when>10:
   u=np.arange(round(.2*SR))/SR
   add(bed,np.sin(2*np.pi*(60*u+4*(1-np.exp(-u*30))))*np.exp(-u*24)*.07,when)
  if i%4==2 and when>17:
   u=np.arange(round(.09*SR))/SR
   add(bed,rng.normal(0,1,len(u))*np.exp(-u*55)*.012,when)
 withdrawal=(t>16.95)&(t<17.2);bed[withdrawal]*=.04
 # Reconstruct documented events at exact simulation ticks. No fabricated kills or explosion.
 def generated(fn):
  raw=getattr(a,fn)(); wf=wave.open(io.BytesIO(raw)); v=np.frombuffer(wf.readframes(wf.getnframes()),dtype='<i2').astype(float)/32768
  return np.interp(np.arange(round(len(v)*SR/wf.getframerate()))*wf.getframerate()/SR,np.arange(len(v)),v)
 cache={}
 mapping={'player_shot':('_gen_gunshot',.30),'enemy_shot':('_gen_gunshot_distant',.20),'enemy_hit':('_gen_bullet_impact_enemy',.19),'reload':('_gen_reload',.22),'footstep':('_gen_footstep',.09),'melee':('_gen_melee_hit',.20)}
 for fn in sorted({v[0] for v in mapping.values()}):
  random.seed(61011+sum(ord(c) for c in fn));cache[fn]=generated(fn)
 cues=[]
 for s in shots:
  if not s['src'].startswith('vertical'):continue
  side=json.loads((OUT/(s['src']+'.foley.json')).read_text())
  for ev in side['events']:
   st=ev['t']/side['hz']
   if s['start']<=st<s['start']+s['duration'] and ev['kind'] in mapping:
    fn,gain=mapping[ev['kind']]
    if fn not in cache:cache[fn]=generated(fn)
    at=s['timeline_in']+st-s['start'];add(fx,cache[fn],at,gain);cues.append(dict(at=round(at,4),kind=ev['kind'],source=s['src'],source_time=st,generator=fn))
 # Only use an existing metal break effect on the visible cinematic rupture.
 for s in shots:
  if s['src']=='cb_crack':
   at=s['timeline_in']+.25;add(fx,generated('_gen_door_rattle'),at,.17);cues.append(dict(at=at,kind='cinematic metal',generator='_gen_door_rattle',note='restraint break sweetening, not added gameplay destruction'))
 end=shots[-1]['timeline_in'];bed[t>=end]*=.42
 mix=bed+fx
 mix*=np.minimum((total-t)/.30,1).clip(0,1)
 peak=float(np.max(np.abs(mix)));mix*=min(1,.86/max(peak,.00001))
 wav=OUT/(name+'.premix.wav')
 with wave.open(str(wav),'wb') as w:w.setparams((1,2,SR,0,'NONE','not compressed'));w.writeframes((mix*32767).astype('<i2').tobytes())
 (OUT/(name+'.audio_cues.json')).write_text(json.dumps(cues,indent=2))
 # Two-pass loudness normalization, mono-safe (centred stereo from mono mix).
 r=command(['ffmpeg','-v','info','-i',wav,'-af','loudnorm=I=-14:TP=-2.5:LRA=9:print_format=json','-f','null','-'])
 stderr=r.stderr.decode(errors='replace'); stats=json.loads(stderr[stderr.rfind('{'):stderr.rfind('}')+1])
 flt='loudnorm=I=-14:TP=-2.5:LRA=9:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:measured_thresh={input_thresh}:offset={target_offset}:linear=true'.format(**stats)
 dest=OUT/(name+'.mix.wav');command(['ffmpeg','-v','error','-y','-i',wav,'-af',flt,'-ar','48000','-ac','2',dest]);return dest

def render(rev,hook='sniper',clean=False):
 shots=make_shots(rev,hook); name=('review_v1' if rev==1 else ('campaign_clean' if clean else ('campaign_final' if hook=='sniper' else 'hook_'+hook)))
 silent=OUT/(name+'.silent.mp4')
 enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920','-r','30','-i','-','-an','-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(silent)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
 for s in shots:
  dec,size=decoder(s); nbytes=size[0]*size[1]*3
  for n in range(round(s['duration']*FPS)):
   data=dec.stdout.read(nbytes)
   if len(data)!=nbytes:raise RuntimeError('Source ended early: '+s['src'])
   im=Image.frombytes('RGB',size,data);im=composition(im,s,not clean,rev,n/FPS)
   enc.stdin.write(im.tobytes())
  dec.stdout.close();dec.wait()
 enc.stdin.close();enc.wait()
 if enc.returncode:raise RuntimeError(enc.stderr.read().decode())
 mix=audio(shots,name)
 final=OUT/(name+'.mp4')
 command(['ffmpeg','-v','error','-y','-i',silent,'-i',mix,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-t',shots[-1]['timeline_out'],'-movflags','+faststart',final])
 for s in shots:
  s.pop('_trace',None);s.pop('_camera',None)
  s['source_path']=str((OUT/(s['src']+'.mp4')).relative_to(ROOT));s['scale']=('360x640 bounded reframe integer nearest 3x' if s.get('reframe_path') else 'native 540x960 integer nearest 2x') if s['src'].startswith('vertical') else ('full broadcast context panel' if s['kind']=='monitor' else 'aspect-preserving cinematic crop');s['audio']='event sidecar -> source-generated game effects + original 108 BPM cue'
 (OUT/(name+'.manifest.json')).write_text(json.dumps(shots,indent=2))
 print('RENDERED',name,shots[-1]['timeline_out'],final.stat().st_size,flush=True)
 return final

def cover():
 b=command(['ffmpeg','-v','error','-ss','7.4','-i',OUT/'vertical2.mp4','-frames:v','1','-f','image2pipe','-vcodec','png','-']).stdout
 im=Image.open(io.BytesIO(b)).convert('RGB').resize((W,H),Image.Resampling.NEAREST)
 # Compose real gameplay hero frame, not a manufactured illustration.
 overlay=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(overlay);d.rectangle((0,0,W,450),fill=(8,14,19,235));d.rectangle((0,1280,W,H),fill=(8,14,19,228));im=Image.alpha_composite(im.convert('RGBA'),overlay)
 small=LOGO.copy();small.thumbnail((780,292));im.alpha_composite(small,(110,195));im=im.convert('RGB')
 text(im,'QUIET ON ROUTE 12',1290,65);text(im,'A campaign under pressure.',1390,43)
 im.save(OUT/'cover.png');print('COVER saved',flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--revision',type=int,default=2);ap.add_argument('--one',action='store_true');args=ap.parse_args()
 render(args.revision)
 if args.revision==2 and not args.one:
  render(2,clean=True);render(2,'warehouse');render(2,'breach');cover()
