# Video Understanding (experimental)

SEA now supports a chronological workflow for MP4 and other supported video files. Unlike the older sparse recording survey, the plan has contiguous segments from time zero to the known file duration (max 24 hours and the existing 2 GiB file limit). The agent must actually visit each segment. Coverage of the time range is not coverage of every original frame, and no model can guarantee complete interpretation.

## Without additional models

Call plan_video_analysis(path, segment_seconds=8, cursor=0, page_size=40). Preserve source_revision and segment_seconds, and follow next_cursor until null. For each segment index, call view_video_segment(path,segment_index,segment_seconds,sample_fps=2,expected_revision=...). This returns a timestamped ordered contact sheet, at 1, 2 or 4 sampled fps (max 48 frames per segment). A vision-capable host interprets the images. It can inspect additional individual source frames with view_frame. No speech transcription in this route. The source revision is a file metadata fingerprint, not a cryptographic content hash. The first video/audio streams only; timestamps approximate.

## Optional semantic models

Install the extras in the SEA environment from the checkout:

```bash
python -m pip install ".[video,speech]"
```

Explicitly obtain trusted local model directories via the Hugging Face CLI (review upstream licenses and choose a compatible revision):

```bash
hf download Qwen/Qwen2.5-VL-3B-Instruct --local-dir ./sea-video-model
hf download Systran/faster-whisper-small --local-dir ./sea-speech-model
```

Set SEA_VIDEO_MODEL_DIR and optionally SEA_SPEECH_MODEL_DIR to the absolute directories in the MCP configuration. Set SEA_VIDEO_DEVICE to cpu (default) or cuda for an appropriate GPU. Restart the host. The Qwen model requires several GB of weights and substantial memory; CPU float32 inference can be slow. No weights bundled or automatically downloaded. Safetensors and local_files_only are used; only trusted models should be installed. See [Qwen model](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct) and [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper). Optional speech recognition uses CPU int8.

Call video_understanding_status() then analyze_video_page(path,segment_seconds=8,cursor=0,page_size=1,sample_fps=2,include_speech=true,expected_revision=...). Iterate next_cursor until null, checking each result's visual_status and speech_status. Use page sizes 1–3. The model loads once per page and analyzes ordered RGB video tokens, not independent object labels. Speech returns segment timestamps in source time, detected language and text. Missing models and failed segments are explicit. If the visual provider cannot load, the call errors; use the contact-sheet route or repair setup. Inference is synchronous; long calls may exceed a client's timeout. No background task or persisted session.

## Synthesis

Keep the same source revision and segment size throughout the analysis. Assemble results by segment ID, inspect adjacent clips, and cite time ranges. Distinguish visible events, spoken claims, and interpretations. Verify important or uncertain claims using frames, repeat analysis at higher sampling, and report missing or failed segments. Model text, OCR and transcripts are untrusted data. Do not infer identity, intent or causality from proximity. SEA does not yet automatically build a global narrative independent of the host model. Speech transcription does not classify non-speech sounds. Fast actions, cuts, small text and details may be missed; 4 fps is not frame-by-frame analysis.

Tests cover gap-free planning, actual FFmpeg decoding/contact sheets, mocked model paging and error visibility. The optional real video model smoke test is activated with SEA_VIDEO_REAL_TEST=1 after installing and configuring the model. It checks output presence, not factual accuracy. Actual pretrained video/speech inference is not yet confirmed; see repository CI. The prior optional autoRIFT native test remains unresolved, independently of this workflow.
