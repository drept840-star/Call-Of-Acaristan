"""Full-decode and measured technical QA; does NOT claim subjective viewing/listening."""
import subprocess,json,hashlib,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
files=['campaign_final.mp4','campaign_clean.mp4','hook_warehouse.mp4','hook_breach.mp4'] if len(sys.argv)==1 else sys.argv[1:]
report={}
for name in files:
 p=OUT/name
 def run(args):return subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 meta=run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)])
 m=json.loads(meta.stdout); v=next(s for s in m['streams'] if s['codec_type']=='video');a=next(s for s in m['streams'] if s['codec_type']=='audio')
 decode=run(['ffmpeg','-v','error','-xerror','-i',str(p),'-f','null','-'])
 loud=run(['ffmpeg','-hide_banner','-i',str(p),'-af','loudnorm=I=-14:TP=-1:LRA=9:print_format=json','-f','null','-'])
 z=loud.stderr;stats=json.loads(z[z.rfind('{'):z.rfind('}')+1])
 pts=run(['ffprobe','-v','error','-select_streams','v','-show_entries','frame=best_effort_timestamp_time','-of','csv=p=0',str(p)])
 times=[float(s.strip(',\n')) for s in pts.stdout.splitlines() if s.strip(',\n')]
 steps=[times[i+1]-times[i] for i in range(len(times)-1)]
 data=p.read_bytes();moov=data.find(b'moov');mdat=data.find(b'mdat')
 report[name]=dict(resolution=[v['width'],v['height']],fps=v['avg_frame_rate'],frames=v.get('nb_frames'),duration=float(m['format']['duration']),video_codec=v['codec_name'],pixel_format=v['pix_fmt'],sar=v.get('sample_aspect_ratio'),audio_codec=a['codec_name'],audio_hz=a['sample_rate'],audio_channels=a['channels'],av_duration_delta=round(abs(float(v['duration'])-float(a['duration'])),6),full_decode_pass=decode.returncode==0,decode_errors=decode.stderr,pts_step_min=min(steps),pts_step_max=max(steps),constant_cadence=all(abs(s-1/30)<.000003 for s in steps),loudness=stats,faststart=0<=moov<mdat,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
 print(name,json.dumps(report[name]),flush=True)
(OUT/'technical_qa.json').write_text(json.dumps(report,indent=2))
