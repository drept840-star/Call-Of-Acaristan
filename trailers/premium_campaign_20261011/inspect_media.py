"""Read-only media inspection bridge; emits JPEG previews, not source changes."""
import sys, subprocess, io, base64
from pathlib import Path
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[2]
def frame(p,t,w=360):
 b=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(ROOT/p),'-frames:v','1','-vf',f'scale={w}:-1','-f','image2pipe','-vcodec','png','-'])
 return Image.open(io.BytesIO(b)).convert('RGB')
def emit(im):
 b=io.BytesIO(); im.save(b,format='JPEG',quality=72); print('IMAGE_BEGIN'); print(base64.b64encode(b.getvalue()).decode()); print('IMAGE_END')
if len(sys.argv)>1:
 emit(frame(sys.argv[1],float(sys.argv[2]),int(sys.argv[3]) if len(sys.argv)>3 else 700))
else:
 sheet=Image.new('RGB',(1080,828),(15,18,22)); d=ImageDraw.Draw(sheet)
 for row,a in enumerate([1,2,3]):
  for col,t in enumerate([1,4,7]):
   im=frame(f'trailers/fresh_action/act{a}.mp4',t)
   sheet.paste(im,(col*360,row*276+24)); d.text((col*360+8,row*276+5),f'ACT {a} / {t}s',fill='white')
 emit(sheet)
