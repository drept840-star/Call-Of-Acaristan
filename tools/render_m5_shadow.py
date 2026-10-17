"""Capture the production M5 finale at 30 fps with native ambience/foley.
Requires ffmpeg on PATH. Does not launch the app or write campaign saves.
Usage: python tools/render_m5_shadow.py --output outputs/M5_Shadow.mp4
Recorded dialogue is not mixed into this review export; the game plays named
VO_192..197 takes through the normal radio voice system when added.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'outputs/M5_Shadow.mp4')
    ap.add_argument('--stills-only',action='store_true')
    args=ap.parse_args();out=args.output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
    # Isolate persistence before importing game config and sound synthesis.
    with tempfile.TemporaryDirectory(prefix='m5_shadow_preview_') as tmp:
        from core import save_system,settings_store,profile_store
        save_system.SAVE_FILE=str(Path(tmp)/'save.json');settings_store.SAVE_FILE=str(Path(tmp)/'settings.json')
        profile_store.PROFILE_FILE=str(Path(tmp)/'profile.json')
        import pygame,numpy as np
        from m5_shadow_check import Harness
        from core.config import audio
        from missions.m5.finale_script import CUES,DURATION_MS
        pygame.init();h=Harness();stills=out.parent/(out.stem+'_stills');stills.mkdir(exist_ok=True)
        samples=(1500,4500,7100,8500,10700,12400,15500,19500,24500,28000,29700,30900,32500,33800,34800,37000,41000)
        try:
            for t in samples:pygame.image.save(h.frame(t),str(stills/f'{t:05}.png'))
            if args.stills_only:print('Stills rendered:',len(samples));return
            # Same game sound generators and effective gains, captured offline.
            pcm={}
            for name in {n for _,n,_ in CUES}|{'rain','wind'}:
                snd=audio.get_sound(name)
                if snd is None:raise RuntimeError('Missing sound '+name)
                arr=pygame.sndarray.array(snd).astype(np.float64)/32768
                if arr.ndim==1:arr=np.repeat(arr[:,None],2,axis=1)
                pcm[name]=arr
            h.fresh();duration=DURATION_MS/1000;sr=pygame.mixer.get_init()[0]
            mix=np.zeros((round(duration*sr),2),np.float64)
            for name in ('rain','wind'):
                arr=pcm[name]*audio._effective_volume(name,.3)
                data=np.tile(arr,(int(np.ceil(len(mix)/len(arr))),1))[:len(mix)]
                edge=round(.10*sr);data[:edge]*=np.linspace(0,1,edge)[:,None];data[-edge:]*=np.linspace(1,0,edge)[:,None]
                mix+=data
            raw=Path(tmp)/'picture.mp4'
            proc=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1000x700','-r','30','-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(raw)],stdin=subprocess.PIPE)
            frames=0
            try:
                for idx in range(1260):
                    pygame.event.pump();s=h.frame(round(idx*1000/30));proc.stdin.write(pygame.image.tobytes(s,'RGB'));frames+=1
                h.at(DURATION_MS);assert h.ends==['MISSION_COMPLETE'],'Production scene did not complete'
            finally:
                proc.stdin.close();code=proc.wait()
            if code:raise RuntimeError('Encoder failed')
            for ms,name,gain in h.audio_events:
                start=round((ms-h.cp.start_time)*sr/1000);arr=pcm[name]*audio._effective_volume(name,gain)
                length=min(len(arr),len(mix)-start)
                if start>=0 and length>0:mix[start:start+length]+=arr[:length]
            peak=float(np.max(np.abs(mix)))
            if peak>.97:mix*=.97/peak
            wav=Path(tmp)/'sound.wav'
            with wave.open(str(wav),'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(mix,-1,1)*32767).astype('<i2').tobytes())
            subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(raw),'-i',str(wav),'-c:v','copy','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(out)],check=True)
            print(f'Production preview: {frames} frames, {duration:g}s, {len(h.audio_events)} cues; audio peak {peak:.3f}; completion once')
        finally:h.close()
if __name__=='__main__':main()
