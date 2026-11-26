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
            evidence_dir=Path(tmp)/'evidence'
            evidence_dir.mkdir()
            env=dict(os.environ,SEA_MEDIA_ROOTS=tmp,SEA_MEMORY_DIR=str(memory_dir),SEA_VISION_WEIGHTS='',SEA_OPEN_VISION_DIR='',SEA_EVIDENCE_DIR=str(evidence_dir))
            params=StdioServerParameters(command=sys.executable,args=['-m','sea.server'],env=env)
            async with stdio_client(params) as (reader,writer):
                async with ClientSession(reader,writer) as session:
                    await session.initialize()
                    tools=await session.list_tools()
                    self.assertEqual({t.name for t in tools.tools},{'inspect_media','sense_media','view_frame','sense_audio','audio_spectrogram','compare_recordings','sense_video','investigate_media','inspect_spatial','inspect_region','sense_signals','investigate_recording','remember_audio','remember_signals','list_perception_memory','recall_perception','compare_perception','forget_perception','read_image_text','compare_images','view_image_difference','find_image_template','guided_workflows','vision_status','detect_objects','view_detections','open_vision_status','find_objects_by_text','view_text_matches','track_objects','view_object_tracks','capture_evidence','list_evidence','recall_evidence','verify_evidence','delete_evidence','measure_micro_motion','view_motion_waveform','autorift_status','measure_displacement','view_displacement_field','video_understanding_status','plan_video_analysis','analyze_video_page','view_video_segment','scan_video_timeline','read_video_frames','view_video_frame_region','compare_video_frames','listen_video_segment'})
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

                    result=await session.call_tool('vision_status',{})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertFalse(data['weights_configured'])
                    result=await session.call_tool('detect_objects',{'path':str(still)})
                    self.assertTrue(result.isError)

                    result=await session.call_tool('open_vision_status',{})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertFalse(data['directory_configured'])
                    result=await session.call_tool('find_objects_by_text',{'path':str(still),'queries':['cat']})
                    self.assertTrue(result.isError)

                    result=await session.call_tool('track_objects',{'path':str(wav),'duration_s':1})
                    self.assertTrue(result.isError)

                    result=await session.call_tool('capture_evidence',{'path':str(wav),'tool':'sense_audio','duration_s':1,'confirm':True})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    key=data['id']
                    result=await session.call_tool('verify_evidence',{'record_id':key,'path':str(wav)})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertTrue(data['source_matches'])
                    result=await session.call_tool('delete_evidence',{'record_id':key,'confirm':True})
                    self.assertFalse(result.isError)

                    import subprocess
                    demo=Path(tmp)/'motion.avi'
                    subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_motion_demo.py'),str(demo)],check=True,timeout=30)
                    result=await session.call_tool('measure_micro_motion',{'path':str(demo),'box':[.1,.1,.9,.9]})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertAlmostEqual(data['frequency_x']['peak_hz'],3,places=2)
                    result=await session.call_tool('view_motion_waveform',{'path':str(demo),'box':[.1,.1,.9,.9]})
                    self.assertFalse(result.isError)
                    self.assertTrue(any(c.type=='image' for c in result.content))

                    result=await session.call_tool('autorift_status',{})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['supported_version'],'2.1.1')
                    result=await session.call_tool('measure_displacement',{'path_a':str(wav),'path_b':str(wav)})
                    self.assertTrue(result.isError)

                    result=await session.call_tool('plan_video_analysis',{'path':str(demo),'segment_seconds':4})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['total_segments'],1)
                    result=await session.call_tool('view_video_segment',{'path':str(demo),'segment_index':0,'segment_seconds':4})
                    self.assertFalse(result.isError)
                    self.assertTrue(any(c.type=='image' for c in result.content))
                    result=await session.call_tool('video_understanding_status',{})
                    self.assertFalse(result.isError)

                    result=await session.call_tool('scan_video_timeline',{'path':str(demo),'segment_seconds':4})
                    self.assertFalse(result.isError)
                    data=result.structuredContent or json.loads(result.content[0].text)
                    self.assertEqual(data['results'][0]['visual_status'],'sampled')
                    result=await session.call_tool('read_video_frames',{'path':str(demo),'count':2})
                    self.assertFalse(result.isError)
                    self.assertEqual(json.loads(result.content[0].text)['frame_indices'],[0,1])
                    self.assertTrue(any(c.type=='image' for c in result.content))
                    result=await session.call_tool('view_video_frame_region',{'path':str(demo),'frame_index':0,'box':[0,0,.5,.5]})
                    self.assertFalse(result.isError)
                    result=await session.call_tool('compare_video_frames',{'path':str(demo),'frame_a':0,'frame_b':1})
                    self.assertFalse(result.isError)
                    audiovisual=Path(tmp)/'perception-av.avi'
                    subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'examples'/'make_demo.py'),str(audiovisual)],check=True,timeout=30)
                    result=await session.call_tool('listen_video_segment',{'path':str(audiovisual),'start_s':2,'duration_s':1})
                    self.assertFalse(result.isError)
                    self.assertTrue(any(c.type=='audio' and c.mimeType=='audio/wav' for c in result.content))
