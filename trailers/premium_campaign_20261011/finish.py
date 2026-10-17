"""Final masters plus two alternate hooks with BIT-IDENTICAL polished video body.
Requires completed campaign_final.silent.mp4 from assemble.py --revision 2 --one.
Run python trailers/premium_campaign_20261011/finish.py
"""
import json,subprocess,wave,sys,hashlib
from pathlib import Path
import numpy as np
import assemble as m
O=m.OUT
# Rebuild/mux corrected true-peak mix without another video generation loss.
shots=m.make_shots(2);mix=m.audio(shots,'campaign_final')
m.command(['ffmpeg','-v','error','-y','-i',O/'campaign_final.silent.mp4','-i',mix,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-t','29.4','-movflags','+faststart',O/'campaign_final.mp4'])
# Stream copy common body at verified keyframe 2.000000. All variants retain original body pixels.
m.command(['ffmpeg','-v','error','-y','-ss','2','-i',O/'campaign_final.silent.mp4','-an','-c:v','copy','-t','27.4',O/'common_body.mp4'])
for hook in ['warehouse','breach']:
 s=m.make_shots(2,hook)[0];name='hook_'+hook
 enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1080x1920','-r','30','-i','-','-an','-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p',str(O/(name+'.opening.mp4'))],stdin=subprocess.PIPE)
 dec,size=m.decoder(s);nb=size[0]*size[1]*3
 from PIL import Image
 for n in range(60):
  d=dec.stdout.read(nb)
  if len(d)!=nb:raise RuntimeError('short hook input')
  enc.stdin.write(m.composition(Image.frombytes('RGB',size,d),s,True,2,n/30).tobytes())
 dec.stdout.close();dec.wait();enc.stdin.close();enc.wait()
 lst=O/(name+'.concat.txt');lst.write_text("file '"+str(O/(name+'.opening.mp4')).replace('\\','/')+"'\nfile '"+str(O/'common_body.mp4').replace('\\','/')+"'\n")
 silent=O/(name+'.silent.mp4');m.command(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',lst,'-c:v','copy','-an',silent])
 altmix=m.audio(m.make_shots(2,hook),name)
 # Keep polished body AUDIO too, not a separately normalized body. Crossfade only within first 2 sec.
 def readwav(p):
  with wave.open(str(p)) as w:return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,w.getnchannels()).copy()
 main=readwav(mix);opening=readwav(altmix);cut=2*m.SR
 n=round(.03*m.SR);blend=np.linspace(0,1,n)[:,None]
 opening[cut-n:cut]=((1-blend)*opening[cut-n:cut]+blend*main[cut-n:cut]).astype('<i2')
 main[:cut]=opening[:cut]
 with wave.open(str(altmix),'wb') as w:w.setparams((2,2,m.SR,0,'NONE','not compressed'));w.writeframes(main.astype('<i2').tobytes())
 m.command(['ffmpeg','-v','error','-y','-i',silent,'-i',altmix,'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000','-t','29.4','-movflags','+faststart',O/(name+'.mp4')])
 manifest=json.loads((O/'campaign_final.manifest.json').read_text());manifest[0].update(s);manifest[0]['source_path']=str((O/(s['src']+'.mp4')).relative_to(m.ROOT));manifest[0]['scale']='native 2x' if s['kind']=='game' else 'aspect-preserving cinematic crop'
 (O/(name+'.manifest.json')).write_text(json.dumps(manifest,indent=2));print('ALT READY',name,flush=True)
 # Verify retained decoded BODY frames match, not just duration or filenames.
 def hashes(p):
  q=m.command(['ffmpeg','-v','error','-i',p,'-map','0:v','-f','framemd5','-']).stdout.decode();return [l.rsplit(',',1)[1].strip() for l in q.splitlines() if not l.startswith('#') and ',' in l]
 orig=hashes(O/'campaign_final.mp4');alt=hashes(O/(name+'.mp4'))
 ok=orig[60:]==alt[60:];print('BODY PIXELS IDENTICAL',name,ok,len(alt),flush=True)
 if not ok:raise RuntimeError('Alternate body changed')
m.render(2,clean=True);m.cover();print('FINISHED',flush=True)
