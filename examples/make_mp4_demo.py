"""Create a six-second, bounded MPEG-4/AAC test clip with exact raw inputs."""
import argparse
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import wave


def make_mp4(output: Path):
    output=output.resolve()
    if output.suffix.lower()!='.mp4' or output.exists():
        raise ValueError('Choose a new .mp4 output path.')
    ffmpeg=shutil.which('ffmpeg')
    if ffmpeg is None:
        raise RuntimeError('FFmpeg is required.')
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        raw=root/'frames.rgb'
        audio=root/'audio.wav'
        raw.write_bytes(b''.join(bytes([255 if 8<=i<16 else 0])*(160*90*3) for i in range(24)))
        with wave.open(str(audio),'wb') as f:
            f.setparams((1,2,16000,0,'NONE','not compressed'))
            f.writeframes(b''.join(struct.pack('<h',int(10000*math.sin(2*math.pi*440*j/16000))
                                  if 32000<=j<64000 else 0) for j in range(96000)))
        # Explicit finite inputs, stream maps, single-threaded encoding, no stdin,
        # and intra frames for reliable segment seeking. No optional encoders.
        args=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-n',
              '-filter_threads','1','-threads','1','-f','rawvideo','-pixel_format','rgb24',
              '-video_size','160x90','-framerate','4','-i',str(raw),
              '-threads','1','-f','wav','-i',str(audio),
              '-map','0:v:0','-map','1:a:0','-c:v','mpeg4','-threads:v','1',
              '-g','1','-bf','0','-q:v','2','-pix_fmt','yuv420p',
              '-c:a','aac','-threads:a','1','-ar','16000','-ac','1',
              '-t','6','-f','mp4',str(output)]
        result=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,timeout=90)
        if result.returncode:
            raise RuntimeError('MP4 fixture encoding failed: '+result.stderr.decode('utf-8','replace')[-4000:])
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    print(make_mp4(parser.parse_args().output))
