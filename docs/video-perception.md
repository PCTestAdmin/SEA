# Universal Video Perception

SEA is a sensory extension, not a reasoning model. An existing vision/audio-capable agent interprets ordered evidence from authorized media. No extra model weights, AI API or new dependency is required. The MCP host may send extracted images/audio to its model provider; obtain permission for sensitive content.

## Recommended workflow

1. Call plan_video_analysis and retain the source_revision, segment_seconds and next_cursor. Whole-file time coverage uses contiguous 4, 8 or 12 second segments. The video must have known duration, up to 24 hours and existing 2 GiB file limit.
2. Call scan_video_timeline for each page (1–3 segments, default 2). Follow next_cursor until null. It returns sampled visual differences, candidate scene changes, audio summary and half-second audio bins; cross-page boundary checks re-read the previous segment. Failed/partial segments and unavailable boundaries are explicit. At 1, 2 or 4 fps, this is not exhaustive original-frame inspection.
3. Optionally use [event relations](event-relations.md) on v0.22 analyze_target pages to connect measured changes. Inspect view_video_segment for every interval using the same plan; do not skip apparently quiet segments. Review original visual evidence, not just numeric candidates. The host supplies semantic reasoning.
4. Inspect consecutive native frame ordinals using read_video_frames. Frames are zero-based decoded presentation order; no resampling or time seeking, and no claim of exact presentation timestamps. Follow next_frame_index, stop at EOF or the explicit 100000 index limit. At most eight frames per call; decoding starts at the beginning and can time out. Native images are downscaled, contact sheets thumbnail them further. For detail use view_video_frame_region (normalized crop on a decoded ordinal) or view_frame (approximate time). Do not convert ordinal to seconds using average FPS on variable-rate video.
5. compare_video_frames compares two decoded ordinals, returning numeric changes and an overlay. No alignment, tracking or semantic equality.
6. listen_video_segment returns a 0.25–12 second first-stream mono 16 kHz WAV plus metadata in the same MCP response. Only use with a compatible host; audio content support at protocol level does not mean every model can hear. If unsupported, use audio measurements and disclose the limitation. No speech or sound labels are generated.

## Report

Build a chronological account from actual observed frames and audible material. Cite segment ID/time or decoded frame ordinal as appropriate. Distinguish what is visible/audible, relationships across events, and uncertain interpretation. Check adjacent segments; verify important changes at higher resolution. A complete time plan is not proof of complete semantic understanding. Report missing or partial evidence and sampling blind spots. Candidate scene changes are simple mean RGB differences and luma histogram distance, not guaranteed edits. Audio and video time offsets are approximate.

No additional AI is required. Older optional model providers remain available but are not the default. The host manages semantic context. The optional [Temporal Index](temporal-index.md) stores frame metadata and explicitly approved host observations across sessions; no model-generated narrative is created. Source revisions detect ordinary metadata changes, not cryptographic authentication.

Tests: [core](../tests/test_video_perception.py) and [MCP round trip](../tests/test_mcp.py). Synthetic AVI fixture validates decoded ordinal order, known visual transitions, crops, difference overlays and actual WAV extraction. It does not establish real-world semantic accuracy. MP4 support relies on FFmpeg's MOV demuxer and supported codecs.
