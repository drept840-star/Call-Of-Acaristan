"""Export the exact procedural M5 mix for audition; no app launch/saves.
No recorded VO is fabricated. Add the game's optional VO takes in-game.
Usage: python tools/export_m5_audio.py --output outputs/M5_audio_preview.wav
"""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import types
import wave

import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/M5_audio_preview.wav')
    args=parser.parse_args()
    # Load only dependency-free script data, not the mission package facade
    # (which would boot config/mixer and touch persistence).
    spec=importlib.util.spec_from_file_location('missions.m5.finale_script',ROOT/'src/missions/m5/finale_script.py')
    script=importlib.util.module_from_spec(spec);spec.loader.exec_module(script)
    sys.modules['missions']=types.ModuleType('missions')
    sys.modules['missions.m5']=types.ModuleType('missions.m5')
    sys.modules['missions.m5.finale_script']=script
    spec=importlib.util.spec_from_file_location('missions.m5.finale_audio',ROOT/'src/missions/m5/finale_audio.py')
    fa=importlib.util.module_from_spec(spec);spec.loader.exec_module(fa)
    STEMS,RATE,stem_pcm,foley_pcm=fa.STEMS,fa.RATE,fa.stem_pcm,fa.foley_pcm
    mix=stem_pcm(STEMS[0]).copy()*.8 + stem_pcm(STEMS[1])*.8*.5
    for ms,name,gain in script.CUES:
        a=round(ms*RATE/1000);pcm=foley_pcm(name)*gain*.8
        length=min(len(pcm),len(mix)-a)
        mix[a:a+length]+=pcm[:length]
    peak=float(np.abs(mix).max());rms=float(np.sqrt(np.mean(mix*mix)))
    if peak>=.98:raise RuntimeError(f'Mix exceeds headroom: {peak:.3f}')
    out=args.output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(out),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(RATE)
        w.writeframes(np.rint(mix*32767).astype('<i2').tobytes())
    print(f'Exported {script.DURATION_MS/1000:g}s stereo; peak {20*np.log10(peak):.1f} dBFS; RMS {20*np.log10(rms):.1f} dBFS; {len(script.CUES)} cues; no recorded VO')


if __name__=='__main__':main()
