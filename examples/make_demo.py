"""Generate a six-second synthetic A/V sample; no third-party content."""
import argparse
from pathlib import Path
import subprocess
import math
import wave
import struct
import tempfile

p=argparse.ArgumentParser()
p.add_argument('output',type=Path)
a=p.parse_args()
if a.output.exists(): raise SystemExit('Refusing to overwrite an existing file.')
with tempfile.TemporaryDirectory() as temp:
    wav=Path(temp)/'test.wav'
    with wave.open(str(wav),'wb') as f:
        f.setparams((1,2,16000,0,'NONE','not compressed'))
        f.writeframes(b''.join(struct.pack('<h',int(10000*math.sin(2*math.pi*440*i/16000)) if 2*16000<=i<4*16000 else 0) for i in range(6*16000)))
    subprocess.run(['ffmpeg','-v','error','-nostdin','-n','-f','lavfi','-i','color=c=black:s=320x180:r=24:d=6', '-i',str(wav),'-vf',"drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='between(t,2,3.999)'",'-c:v','mpeg4','-c:a','aac','-t','6',str(a.output)],check=True)
print(a.output.resolve())
