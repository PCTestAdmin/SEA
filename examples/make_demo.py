"""Finite AVI test fixture: pure Python, no encoder or third-party content."""
import argparse
import math
import struct
from pathlib import Path


def chunk(kind,data):
    return kind+struct.pack('<I',len(data))+data+b'\0'*(len(data)%2)


def group(kind,*parts):
    return chunk(b'LIST',kind+b''.join(parts))


def make_demo(output: Path):
    if output.suffix.lower()!='.avi':
        raise ValueError('Choose an .avi output filename.')
    w,h,fps,rate,n=160,90,4,16000,24
    frame=w*h*3
    block=rate//fps*2
    avih=struct.pack('<14I',250000,frame*fps+rate*2,0,0x10,n,0,2,max(frame,block),w,h,0,0,0,0)
    def stream(kind,handler,scale,rate,length,buffer,sample,rect):
        return struct.pack('<4s4sIHH8I4h',kind,handler,0,0,0,0,scale,rate,0,length,buffer,0xffffffff,sample,*rect)
    v=group(b'strl',chunk(b'strh',stream(b'vids',b'DIB ',1,fps,n,frame,0,(0,0,w,h))),
            chunk(b'strf',struct.pack('<IiiHHIIiiII',40,w,h,1,24,0,frame,0,0,0,0)))
    a=group(b'strl',chunk(b'strh',stream(b'auds',b'\0'*4,2,rate*2,rate*6,block,2,(0,0,0,0))),
            chunk(b'strf',struct.pack('<HHIIHH',1,1,rate,rate*2,2,16)))
    parts,index=[],[]
    offset=4
    for i in range(n):
        pixels=bytes([255 if 8<=i<16 else 0])*frame
        audio=b''.join(struct.pack('<h',int(10000*math.sin(2*math.pi*440*j/rate)) if 32000<=j<64000 else 0)
                       for j in range(i*rate//fps,(i+1)*rate//fps))
        for kind,data in ((b'00db',pixels),(b'01wb',audio)):
            c=chunk(kind,data)
            index.append(struct.pack('<4sIII',kind,16,offset,len(data)))
            parts.append(c)
            offset+=len(c)
    payload=b'AVI '+group(b'hdrl',chunk(b'avih',avih),v,a)+group(b'movi',*parts)+chunk(b'idx1',b''.join(index))
    with output.open('xb') as f:
        f.write(chunk(b'RIFF',payload))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    make_demo(args.output)
    print(args.output.resolve())


if __name__=='__main__':
    main()
