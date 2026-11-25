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
                    self.assertEqual({t.name for t in tools.tools},{'inspect_media','sense_media','view_frame','sense_audio','audio_spectrogram','compare_recordings','sense_video','investigate_media','inspect_spatial','inspect_region'})
                    result=await session.call_tool('sense_media',{'path':str(wav),'duration_s':1})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['observations']['low_level_bins'],2)

                    result=await session.call_tool('sense_audio',{'path':str(wav),'duration_s':1})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['events'],[])
                    image=await session.call_tool('audio_spectrogram',{'path':str(wav),'duration_s':1})
                    self.assertFalse(image.isError)
                    self.assertTrue(any(c.type=='image' and c.mimeType=='image/png' for c in image.content))
                    result=await session.call_tool('compare_recordings',{'path_a':str(wav),'path_b':str(wav),'duration_s':1})
                    self.assertFalse(result.isError)

                    result=await session.call_tool('investigate_media',{'path':str(wav),'duration_s':1})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['available_modalities'],{'audio':True,'video':False})
                    result=await session.call_tool('sense_video',{'path':str(wav),'duration_s':1})
                    self.assertTrue(result.isError)

                    from sea.acoustics import png
                    import numpy as np
                    still=Path(tmp)/'still.png'
                    still.write_bytes(png(np.zeros((32,32,3),dtype=np.uint8)))
                    result=await session.call_tool('inspect_spatial',{'path':str(still)})
                    self.assertFalse(result.isError)
                    result=await session.call_tool('inspect_region',{'path':str(still),'box':[0,0,.5,.5]})
                    self.assertFalse(result.isError)
                    self.assertTrue(any(c.type=='image' for c in result.content))
