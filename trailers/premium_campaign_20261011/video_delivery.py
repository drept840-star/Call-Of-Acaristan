"""Private binary delivery over the text-only MCP, within its 262144-byte output limit."""
import sys,hashlib,base64
from pathlib import Path
p=Path(__file__).resolve().parent/'campaign_final.mp4'
i=int(sys.argv[1]); assert 0<=i<100
with p.open('rb') as f:
 f.seek(i*190000); b=f.read(196000 if i==99 else 190000)
print('VIDEO_CHUNK',i,len(b),hashlib.sha256(b).hexdigest())
print('VIDEO_BEGIN');print(base64.b64encode(b).decode());print('VIDEO_END')
