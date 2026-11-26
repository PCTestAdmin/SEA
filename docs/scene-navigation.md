# Evidence-based scene navigation

SEA does not understand the meaning of a scene on its own. This read-only tool helps a host model navigate a large sampled evidence batch without rereading every comparison record.

1. Run `sea analyze /absolute/path/video.mp4 --segment-seconds 4 --page-size 2` and save the JSON envelope. Follow its next_cursor until null using the same revision and settings.
2. Audit up to 16 envelopes with `sea audit-video-coverage page0.json page1.json`.
3. Run `sea summarize-video-scenes page0.json page1.json --limit 20` (MCP: summarize_video_scenes). Continue using next_offset. Do not mix source revisions or overlapping pages.
4. Inspect representative timestamps with view_frame or view_video_segment; verify finer details and actions using read_video_frames. Use relate_video_events for candidate temporal associations.

## Interpretation

- Scene ranges cover the full declared duration, including missing evidence. A candidate cut or an unavailable boundary starts a new range; neither proves a semantic scene transition.
- Independent audio coverage reports measured seconds, low-level observed seconds, known absent-stream seconds and unknown seconds. Unknown is not silence. Frequencies summarize overlapping half-second bins; partial-bin allocation is approximate.
- Sample timestamps reference the original segment and evidence digest. They are approximate sampling times, not native frame ordinals or exact source PTS.
- Up to 50 ranges per response; scene IDs are local to the exact batch. For long videos, audit and summarize separate batches, keeping global gap accounting. Batch boundaries may split scenes.
- No source read, no new model, no storage, no causal interpretation. A digest checks internal consistency, not authenticity.
