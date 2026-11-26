"""Generate a synthetic 3 Hz, 0.4 sampled-pixel motion clip without FFmpeg encoding."""
import argparse
from pathlib import Path
import struct
import numpy as np

def chunk(kind,data):
    return kind+struct.pack('<I',len(data))+data+b'\0'*(len(data)%2)

def group(kind,*parts):
    return chunk(b'LIST',kind+b''.join(parts))

def write_avi(path,frames,fps):
    n,h,w=frames.shape
    if w%4:
        raise ValueError('Fixture width must be divisible by four.')
    size=w*h*3
    avih=struct.pack('<14I',round(1e6/fps),size*fps,0,16,n,0,1,size,w,h,0,0,0,0)
    sh=struct.pack('<4s4sIHH8I4h',b'vids',b'DIB ',0,0,0,0,1,fps,0,n,size,0xffffffff,0,0,0,w,h)
    sf=struct.pack('<IiiHHIIiiII',40,w,h,1,24,0,size,0,0,0,0)
    chunks=[];index=[];offset=4
    for frame in frames:
        data=np.repeat(frame[::-1,:,None],3,axis=2).tobytes()
        c=chunk(b'00db',data)
        chunks.append(c);index.append(struct.pack('<4sIII',b'00db',16,offset,len(data)))
        offset+=len(c)
    payload=b'AVI '+group(b'hdrl',chunk(b'avih',avih),group(b'strl',chunk(b'strh',sh),chunk(b'strf',sf)))+group(b'movi',*chunks)+chunk(b'idx1',b''.join(index))
    with path.open('xb') as f:f.write(chunk(b'RIFF',payload))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    args=p.parse_args()
    y,x=np.mgrid[:80,:96].astype(float)
    frames=[]
    for i in range(96):
        dx=.4*np.sin(2*np.pi*3*i/24)
        frames.append(np.clip(128+40*np.sin((x-dx)*.26)+36*np.cos(y*.31)+20*np.sin((x-dx+y)*.19),0,255).astype(np.uint8))
    write_avi(args.output,np.stack(frames),24)
    print(args.output.resolve())

if __name__=='__main__':main()
