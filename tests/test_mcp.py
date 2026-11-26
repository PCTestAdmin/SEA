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
            memory_dir=Path(tmp)/'memory'
            memory_dir.mkdir()
            env=dict(os.environ,SEA_MEDIA_ROOTS=tmp,SEA_MEMORY_DIR=str(memory_dir))
            params=StdioServerParameters(command=sys.executable,args=['-m','sea.server'],env=env)
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer) as session:
                    await session.initialize()
                    tools=await session.list_tools()
                    self.assertEqual({t.name for t in tools.tools},{'inspect_media','sense_media','view_frame','sense_audio','audio_spectrogram','compare_recordings','sense_video','investigate_media','inspect_spatial','inspect_region','sense_signals','investigate_recording','remember_audio','remember_signals','list_perception_memory','recall_perception','compare_perception','forget_perception','read_image_text','compare_images','view_image_difference','find_image_template','guided_workflows'})
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

                    csv=Path(tmp)/'signals.csv'
                    csv.write_text('t,x,y\n0,1,2\n1,2,4\n',encoding='utf-8')
                    result=await session.call_tool('sense_signals',{'path':str(csv),'time_column':'t','channels':['x','y']})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['same_row_correlations'][0]['pearson_r'],1)

                    result=await session.call_tool('investigate_recording',{'path':str(wav),'span_s':1,'max_refinements':0})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['scan_windows'][0]['status'],'scanned')

                    result=await session.call_tool('remember_audio',{'path':str(wav),'label':'baseline','duration_s':1})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    record_id=data['id']
                    result=await session.call_tool('recall_perception',{'record_id':record_id})
                    self.assertFalse(result.isError)
                    result=await session.call_tool('forget_perception',{'record_id':record_id,'confirm':True})
                    self.assertFalse(result.isError)

                    result=await session.call_tool('compare_images',{'path_a':str(still),'path_b':str(still)})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['changed_pixel_fraction'],0)
                    result=await session.call_tool('guided_workflows',{})
                    self.assertFalse(result.isError)
