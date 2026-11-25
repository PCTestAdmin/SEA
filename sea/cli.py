"""Standalone diagnostics for testing the perception engine without an MCP host."""
import argparse
import json
from .engine import analyze, resolve_media

def main():
    p=argparse.ArgumentParser(description='SEA local diagnostic measurement')
    p.add_argument('path')
    p.add_argument('--start',type=float,default=0)
    p.add_argument('--duration',type=float,default=15)
    a=p.parse_args()
    print(json.dumps(analyze(resolve_media(a.path),a.start,a.duration),indent=2,allow_nan=False))

if __name__=='__main__':main()
