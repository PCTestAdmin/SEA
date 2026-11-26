"""Generate a finite six-second synthetic A/V sample; no third-party content."""
import argparse
from pathlib import Path
import subprocess
import math
import wave
import struct
import tempfile


def make_demo(output: Path) -> None:
    if output.exists():
        raise FileExistsError('Refusing to overwrite an existing file.')
    with tempfile.TemporaryDirectory() as temp:
        wav=Path(temp)/'test.wav'
        video=Path(temp)/'frames.yuv'
        with wave.open(str(wav),'wb') as f:
            f.setparams((1,2,16000,0,'NONE','not compressed'))
            f.writeframes(b''.join(struct.pack('<h',int(10000*math.sin(2*math.pi*440*i/16000)) if 32000<=i<64000 else 0) for i in range(96000)))
        # Finite YUV420p input, avoiding lavfi and drawbox on Windows.
        w,h,fps=320,180,24
        chroma=bytes([128])*(w*h//2)
        black=bytes([16])*(w*h)+chroma
        white=bytes([235])*(w*h)+chroma
        with video.open('wb') as f:
            for i in range(6*fps):
                f.write(white if 2*fps<=i<4*fps else black)
        encoded=Path(temp)/'demo.mp4'
        subprocess.run(['ffmpeg','-v','error','-nostdin','-n',
                        '-threads','1','-f','rawvideo','-pixel_format','yuv420p',
                        '-video_size','320x180','-framerate','24','-i',str(video),
                        '-threads','1','-i',str(wav),'-map','0:v:0','-map','1:a:0',
                        '-c:v','mpeg4','-c:a','aac','-threads','1','-t','6',str(encoded)],
                       check=True,stdin=subprocess.DEVNULL,timeout=30)
        # Publish only a complete result; preserve an existing destination.
        with output.open('xb') as f:
            f.write(encoded.read_bytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    make_demo(args.output)
    print(args.output.resolve())


if __name__=='__main__':
    main()
