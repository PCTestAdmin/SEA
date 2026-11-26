"""Materialize a frozen, six-second MPEG-4/AAC synthetic fixture.

The payload is gzip-compressed base64 solely to keep the small fixture textual
and reviewable in Git. Generated with FFmpeg 7.1.5 from 24 RGB frames at 4 fps
(32x18, black/white/black) and 288000 mono 48 kHz PCM samples (375 Hz sine
from 2 to 4 s, amplitude 10000). Encoding: mpeg4, intra frames, no B frames,
yuv420p, q:v 2, AAC 12k, six seconds, explicit audio/video mapping.
No runtime encoder is needed; the exact media bytes are verified before use.
"""
import argparse
import base64
import gzip
import hashlib
from pathlib import Path

SHA256 = '9fc63488526f47f6fa1a48c91bdaaa712ed8eebf5504b3a0de4bf2641c456284'
_PAYLOAD = (
    'H4sIAAAAAAAC/+1ZfUxbVRQ/77XQMRhSSikbHZQETFz4HqJEhYImlE3FTF2yuDkLr0BdH619jypu'
    'SOd0gBNNZuKSZY74h0vI/kBlgslY5iYJwRmIf/gxpm5Jt+FHJuA2YSKt570+7C3rCB+VxPhe+PXd'
    'd94559577u+dc3MBAH0N3+iwcnYWgAbhjshnHQV5ALCqxmmxAOhcLGPmf6ThUbOrujAvO68oOy83'
    'D+hcYywA1Q1xKrz1aOg31ddOt/d4Cy9MXbBfpJIMqsWA8KQLm6fksHlKXbonv5fysMWoPGwxKg9b'
    'jMqXHCMjotWWce5d09nise6JKV/vjG/LwPEUI1RGbdjTqNL0rSrdRkenRP+uXH+mbezyC0Obz054'
    'iwZferakbD8NVP6+R9ygfi0/zQgq/eW+nFTPkUOve/7iDo73NR07PLP7Ytfum2NlN3LKJv0jbZHW'
    'YT1LjHTTL5n9V0YfmLp68+pYW2dnATAV79y9pUNx4ttjj02Mn++enm7xFtNNM2e8xTEPCb/3U3Eb'
    'Vr/d7PH9VukrGfUMd5zwVXi7vV2eGUVn0ZdV++Oj0m782VS8N7244/EXj5ruenCSikeDnQO+7zu8'
    'zcO9vWhQPtlxvaTrVlTFULW6rFTUfNXEnRq6PkiNHr0k6/+39Al26eawS46crB8eZiXLzJL1F8SU'
    'VJkpsn64mTUQau8kR07WDw+z5H2TrP/vMEveN8n6C2OKvG/6f+lXbYp/o+v89MTxUzvOHdwOAIlZ'
    '3aPDPSnfNY6Pj//xuXR9kyJcqZ9R2a0jg7l76ZKSt1pO7vmofafIHHXo889Liz9HUy/3/JPwEo5z'
    'PfVyzz4DnsJ2/qleyvlnyMPrEG6TwzbAZQctOou1213ISBvrqmMg6FL8BKBzAAXCX+CigrXmPhth'
    '3ksBQPfyTvMubG/nd4l9Km73hv3C/P2E7NeAiBcf0y0Mz+Fdb7FxfMBC8iva0jksYzULViwzd+7o'
    'jXLD0/3iQ1YdY3POvnFZGQupuRWf7SZzPWOzCDrUCGutr8FGgosVnZLDTGf87/SM01JDTCOmwWkz'
    '+NvUYY6vsmF7hOM5htD5gnUUuO4QCmHi8WDCu2lWQxPERAPrsNQWBFkk+Xz4+5yFYzhxXdxudyU6'
    'VuK91KAWRWswCgpjBEpy0OOHwug+adP4u6cM0N/eChmUkn6qGh8/DuovEm0oWohCFe/0h1/yJvTM'
    '8eLSzM4kCSBOaOtxxtWEnEQCvntZerfObwMOjq+2z84GUYo4gPgaTVIRuExUF+IWLvXDiGsAEZsB'
    'VB8ARA1j0O8BiN2Hff8AoMFPQYv2WrTXfoX5ORmB9olor4tEPIF2789DWzoEbSlq8Z/LPLRVSraq'
    'tXem7Uk3KK0hacvZG+pJzSfxmQnQNrJfom0cxwY5XQBlI1slyr4yh7L1SFnzbdOm/KuNQxWuQpKA'
    'GRhHgYA6o1Z8mY2bpmSPQMAIdevWKxCCVpKOEA6CVqhDrRNDBv/kr08JesXOoZfgM0ZqRyCipXYk'
    'IY8i5KsJeQwhX0PI4wi5mpBrCHkCIdcR8qSAXOkmqC+IkJoghEcpY8VRh9iIEP5vnStjRZAjfT8y'
    '/wJYye+fJ8rsWkQm4hkEllEYw3xUhGhGDGIaxdxG78BcjuU0Asun6jSmzZ8xlWH5jX0PU+Ikpr80'
    'HD7aa9Fe+yuW2HsRaJ+I9jqsKLrnhRLP1ToYIRE67TablJ8pccOi56pqxSIrvaGkjCgomxsYXqg3'
    '21gLP1t30sgiiIXTaXY4bGQhzLT6K216J2+3i4XOLBqLNQM3NTW4qbkP9zQb/wZ7AD+MxyIAAA=='
)


def make_mp4(output: Path):
    output = output.resolve()
    if output.suffix.lower() != '.mp4':
        raise ValueError('Choose a new .mp4 output path.')
    data = gzip.decompress(base64.b64decode(_PAYLOAD, validate=True))
    if len(data) != 8903 or hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError('Frozen MP4 fixture integrity check failed.')
    # Exclusive creation prevents overwriting an existing user file.
    with output.open('xb') as f:
        f.write(data)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    print(make_mp4(parser.parse_args().output))
