"""Small process-local LRU of compact measurements, never raw images or audio."""
from collections import OrderedDict
from threading import RLock
from time import monotonic
import json
import os

MAX_ENTRIES=128
MAX_BYTES=256*1024
TTL_S=300


class ScanCache:
    def __init__(self,max_entries=MAX_ENTRIES,max_bytes=MAX_BYTES,ttl=TTL_S,clock=monotonic):
        self.max_entries=max_entries
        self.max_bytes=max_bytes
        self.ttl=ttl
        self.clock=clock
        self.lock=RLock()
        self.entries=OrderedDict()
        self.size=0

    def _remove(self,key):
        _,payload=self.entries.pop(key)
        self.size-=len(payload)

    def _expire(self,now):
        for key,(expires,_) in list(self.entries.items()):
            if expires<=now:
                self._remove(key)

    def get(self,key):
        with self.lock:
            self._expire(self.clock())
            item=self.entries.get(key)
            if item is None:
                return None
            self.entries.move_to_end(key)
            return json.loads(item[1])

    def put(self,key,value):
        payload=json.dumps(value,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('ascii')
        if len(payload)>self.max_bytes:
            return
        with self.lock:
            now=self.clock()
            self._expire(now)
            if key in self.entries:
                self._remove(key)
            self.entries[key]=(now+self.ttl,payload)
            self.size+=len(payload)
            while len(self.entries)>self.max_entries or self.size>self.max_bytes:
                self._remove(next(iter(self.entries)))

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.size=0


CACHE=ScanCache()


def enabled():
    return os.environ.get('SEA_SCAN_CACHE','on').strip().lower() not in ('off','0','false')
