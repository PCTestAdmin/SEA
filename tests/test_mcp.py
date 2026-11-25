"""Real SDK client/stdio round trip. CI requires the SDK; offline core tests may skip."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import wave

@unittest.skipUnless(importlib.util.find_spec('mcp'), 'MCP SDK not installed')
class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_and_result(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as tmp:
            wav=Path(tmp)/'silence.wav'
            with wave.open(str(wav),'wb') as f:
                f.setparams((1,2,16000,0,'NONE','not compressed'))
                f.writeframes(b'\0' * 32000)
            env=dict(os.environ,SEA_MEDIA_ROOTS=tmp)
            params=StdioServerParameters(command=sys.executable,args=['-m','sea.server'],env=env)
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer) as session:
                    await session.initialize()
                    tools=await session.list_tools()
                    self.assertEqual({t.name for t in tools.tools},{'inspect_media','sense_media','view_frame'})
                    result=await session.call_tool('sense_media',{'path':str(wav),'duration_s':1})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['observations']['low_level_bins'],2)
