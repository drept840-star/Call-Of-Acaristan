"""Private MCP transfer bridge. No networking, hosting, or public upload.
Build a user-friendly ZIP; solid xz transport avoids retransmitting identical alternate bodies.
Run with no args to package, or --chunk N to read one base64 chunk.
"""
import sys,json,zipfile,lzma,hashlib,base64
from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parents[1];CHUNK=4_000_000
zip_path=O/'Call_of_Acaristan_campaign_package.zip';xz=O/'package_transport.xz'
if '--chunk' in sys.argv:
 i=int(sys.argv[-1]);
 with xz.open('rb') as f:f.seek(i*CHUNK);data=f.read(CHUNK)
 print('CHUNK_BEGIN');print(base64.b64encode(data).decode());print('CHUNK_END')
else:
 names=['campaign_final.mp4','campaign_clean.mp4','hook_warehouse.mp4','hook_breach.mp4','cover.png','assemble.py','capture.py','capture_vertical.py','finish.py','verify.py','README.md','QA.md','technical_qa.json','capture_report.json','vertical_report.json','smoke.log','finish.log','campaign_final.mix.wav','campaign_final.premix.wav']
 names += [p.name for p in O.glob('*.manifest.json') if not p.name.startswith('review')]
 names += [p.name for p in O.glob('*.audio_cues.json') if not p.name.startswith('review')]
 for s in ['vertical1','vertical2','vertical3']:
  names += [s+'.mp4',s+'.trace.json',s+'.foley.json']
 names += [s+'.mp4' for s in ['monitor_broadcast','cb_crack','k9_firstperson_grab']]
 with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_STORED) as z:
  for n in names:z.write(O/n,'trailers/premium_campaign_20261011/'+n)
 with zip_path.open('rb') as src,lzma.open(xz,'wb',format=lzma.FORMAT_XZ,filters=[{'id':lzma.FILTER_LZMA2,'preset':6,'dict_size':1<<26}]) as dst:
  while b:=src.read(1024*1024):dst.write(b)
 info={'zip_bytes':zip_path.stat().st_size,'zip_sha256':hashlib.sha256(zip_path.read_bytes()).hexdigest(),'transport_bytes':xz.stat().st_size,'transport_sha256':hashlib.sha256(xz.read_bytes()).hexdigest(),'chunk_size':CHUNK,'chunks':(xz.stat().st_size+CHUNK-1)//CHUNK,'files':len(names)}
 (O/'package_info.json').write_text(json.dumps(info,indent=2));print(json.dumps(info),flush=True)
