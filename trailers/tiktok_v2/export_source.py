"""Export native-resolution footage without a low-resolution intermediate."""
import subprocess, shutil, pathlib, base64, sys, hashlib
root=pathlib.Path(__file__).resolve().parents[2]
out=root/'trailers/tiktok_v2/native_source.mp4'
if len(sys.argv)>1:
    data=out.read_bytes()
    print('CHUNK_BEGIN')
    print(base64.b64encode(data[int(sys.argv[1])*180000:(int(sys.argv[1])+1)*180000]).decode())
    print('CHUNK_END')
else:
    f=shutil.which('ffmpeg')
    a=[f,'-v','error','-y']
    for p,start in [('act2.mp4','3'),('act3.mp4','1'),('act1.mp4','1')]:
        a+=['-ss',start,'-t','4','-i',str(root/'trailers/fresh_action'/p)]
    graph=';'.join('[%d:v]setpts=PTS-STARTPTS[v%d]'%(i,i) for i in range(3))+';[v0][v1][v2]concat=n=3:v=1:a=0[v]'
    subprocess.run(a+['-filter_complex',graph,'-map','[v]','-an','-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],check=True)
    d=out.read_bytes()
    print('bytes',len(d),'chunks',(len(d)+179999)//180000,'sha256',hashlib.sha256(d).hexdigest())
