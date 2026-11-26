"""Bounded adapter for the optional NASA JPL autoRIFT 2.1.1 provider."""
from __future__ import annotations
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
from PIL import Image, ImageDraw
from .images import load_still
from .vision import fingerprint
from .acoustics import png

VERSION='2.1.1'
MAX_SIDE=768
CHIP=32
STEP=32
COARSE_SAMPLE_RATE=1
MAX_OUTPUT=512*1024


def status():
    try:
        version=importlib.metadata.version('geo_autoRIFT')
    except importlib.metadata.PackageNotFoundError:
        version=None
    present=importlib.util.find_spec('autoRIFT') is not None
    return {'provider':'NASA JPL autoRIFT','supported_version':VERSION,
            'installed_version':version,'module_discoverable':present,
            'ready_to_attempt':present and version==VERSION,
            'note':'Package discovery only; real native execution is tested separately.'}


def grid(width,height,search):
    if not isinstance(search,int) or isinstance(search,bool) or not 6<=search<=24:
        raise ValueError('Search radius must be an integer from 6 to 24 sample pixels.')
    if not 1<=width<=MAX_SIDE or not 1<=height<=MAX_SIDE:
        raise ValueError('Unsupported sampled dimensions.')
    margin=CHIP//2+search+4
    # Upstream regular grid uses integer one-based centers.
    x=np.arange(margin+1,width-margin+1,STEP,dtype=np.int32)
    y=np.arange(margin+1,height-margin+1,STEP,dtype=np.int32)
    if min(len(x),len(y))<8:
        raise ValueError('Need at least eight grid locations per axis; use larger images or a smaller search radius.')
    return np.meshgrid(x,y)


def normalize(x,y,dx,dy,chip,interp,search):
    if any(a.shape!=x.shape for a in (y,dx,dy,chip,interp)):
        raise ValueError('Unexpected autoRIFT output dimensions.')
    rows=[]
    for i in np.ndindex(x.shape):
        valid=bool(np.isfinite(dx[i]) and np.isfinite(dy[i]) and
                   chip[i]>0 and abs(dx[i])<=search+.5 and abs(dy[i])<=search+.5)
        kind='interpolated' if valid and interp[i] else 'matched' if valid else 'missing'
        rows.append({'grid_x_1based':int(x[i]),'grid_y_1based':int(y[i]),
                     'dx_autorift_px':round(float(dx[i]),6) if valid else None,
                     'dy_autorift_px':round(float(dy[i]),6) if valid else None,
                     'chip_size_px':int(chip[i]) if valid else None,'status':kind})
    direct=[r for r in rows if r['status']=='matched']
    return {'grid_shape':list(x.shape),'points':rows,
            'matched_count':len(direct),'interpolated_count':sum(r['status']=='interpolated' for r in rows),
            'missing_count':sum(r['status']=='missing' for r in rows),
            'median_matched_dx_px':float(np.median([r['dx_autorift_px'] for r in direct])) if direct else None,
            'median_matched_dy_px':float(np.median([r['dy_autorift_px'] for r in direct])) if direct else None}


def native(a,b,search):
    """Only invoked in the separate worker (or explicit real-provider tests)."""
    if not status()['ready_to_attempt']:
        raise RuntimeError('Install autoRIFT 2.1.1 in the SEA environment; see docs/displacement.md.')
    from autoRIFT import autoRIFT
    if a.ndim!=2 or b.shape!=a.shape or a.dtype!=np.uint8 or b.dtype!=np.uint8:
        raise ValueError('Expected equal-size uint8 grayscale images.')
    h,w=a.shape
    x,y=grid(w,h,search)
    obj=autoRIFT()
    obj.I1=np.ascontiguousarray(a)
    obj.I2=np.ascontiguousarray(b)
    obj.xGrid=x.copy()
    obj.yGrid=y.copy()
    obj.ChipSizeMinX=CHIP
    obj.ChipSizeMaxX=CHIP
    obj.ChipSize0X=CHIP
    obj.GridSpacingX=STEP
    obj.SkipSampleX=STEP
    obj.SkipSampleY=STEP
    obj.SearchLimitX=search
    obj.SearchLimitY=search
    obj.MultiThread=0
    obj.OverSampleRatio=16
    # autoRIFT's default coarse stride of four is intended for large grids.
    # On SEA's 14x14 fixture it creates a 3x3 coarse grid. The upstream
    # 5x5 neighborhood filter still requires eight agreeing samples,
    # eliminating edge cells and then the remaining center on iteration 2.
    # Use the full bounded grid for coarse matching; keep all upstream
    # consistency thresholds, iterations and fine subpixel filtering intact.
    obj.sparseSearchSampleRate=COARSE_SAMPLE_RATE
    obj.runAutorift()
    return normalize(x,y,obj.Dx,obj.Dy,obj.ChipSizeX,obj.InterpMask,search)


def worker(input_path,output_path):
    with np.load(input_path,allow_pickle=False) as data:
        result=native(data['a'],data['b'],int(data['search']))
    raw=json.dumps(result,allow_nan=False,separators=(',',':')).encode()
    if len(raw)>MAX_OUTPUT:
        raise RuntimeError('Provider result exceeds limit.')
    with open(output_path,'xb') as f:
        f.write(raw)


def measure(a_path:Path,b_path:Path,search:int=12):
    if not status()['ready_to_attempt']:
        raise ValueError('Optional autoRIFT 2.1.1 is unavailable; see docs/displacement.md.')
    before=(fingerprint(a_path),fingerprint(b_path))
    a,sa=load_still(a_path,MAX_SIDE)
    b,sb=load_still(b_path,MAX_SIDE)
    if sa!=sb or a.shape!=b.shape:
        raise ValueError('Images must have identical source dimensions.')
    h,w=a.shape[:2]
    grid(w,h,search)
    gray=lambda rgb:np.asarray(Image.fromarray(rgb).convert('L'))
    ga,gb=gray(a),gray(b)
    if min(float(ga.std()),float(gb.std()))<2:
        raise ValueError('Images lack sufficient global contrast.')
    with tempfile.TemporaryDirectory(prefix='sea-autorift-') as tmp:
        inp=Path(tmp)/'input.npz'
        out=Path(tmp)/'output.json'
        np.savez(inp,a=ga,b=gb,search=search)
        env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_NUM_THREADS='1')
        try:
            p=subprocess.run([sys.executable,'-m','sea.displacement',str(inp),str(out)],
                             stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                             timeout=90,check=False,env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError('autoRIFT timed out; try a smaller image pair.') from None
        if p.returncode or not out.is_file() or out.stat().st_size>MAX_OUTPUT:
            raise RuntimeError('autoRIFT provider failed; verify the pinned Conda environment.')
        result=json.loads(out.read_bytes())
    if before!=(fingerprint(a_path),fingerprint(b_path)):
        raise RuntimeError('Source changed during displacement analysis.')
    return {'provider':'NASA JPL autoRIFT','provider_version':VERSION,'a':a_path.name,'b':b_path.name,
            'source_size_px':sa,'sample_size_px':[w,h],'search_radius_px':search,
            'chip_size_px':CHIP,'grid_spacing_px':STEP,'coarse_search_stride':COARSE_SAMPLE_RATE,**result,
            'limitations':['Raw autoRIFT displacement convention: Cartesian y is positive upward, grid rows increase downward.',
                           'Vectors are sampled-image pixels, not meters or velocities. Direction convention should be checked with a known reference pair.',
                           'Fixed single chip size, grayscale, no georeferencing, automatic alignment or orthorectification.',
                           'Matched means accepted by the upstream algorithm, not verified correspondence; interpolated points are not direct measurements.',
                           'Changes in viewpoint, illumination, repeating texture or occlusion may yield missing or wrong matches. No diagnosis.']},a


def draw_vectors(report,rgb):
    im=Image.fromarray(rgb.copy())
    d=ImageDraw.Draw(im)
    for row in report['points']:
        x,y=row['grid_x_1based']-1,row['grid_y_1based']-1
        if row['status']=='missing':
            d.ellipse((x-2,y-2,x+2,y+2),fill='#808080')
            continue
        # Native Cartesian coordinates converted to image coordinates; not a registered warp.
        u=x+row['dx_autorift_px']*2
        v=y-row['dy_autorift_px']*2
        c='#ffbf69' if row['status']=='interpolated' else '#00e5ff'
        d.line((x,y,u,v),fill=c,width=2)
        d.ellipse((u-2,v-2,u+2,v+2),fill=c)
    d.rectangle((0,0,im.width,20),fill='#102331')
    d.text((5,4),'autoRIFT raw vectors x2 | cyan matched | orange interpolated | gray missing',fill='white')
    return png(np.asarray(im))


if __name__=='__main__':
    if len(sys.argv)!=3:
        raise SystemExit('Internal worker expects input and output files.')
    worker(sys.argv[1],sys.argv[2])
