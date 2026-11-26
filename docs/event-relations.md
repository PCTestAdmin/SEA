# Spatiotemporal event relations (v0.22)

SEA measures image and audio changes; the host supplies semantic interpretation. Generate portable pages with analyze_target or sea analyze using consistent sample_fps and segment_seconds, then audit coverage and call relate_video_events (MCP), or:

```bash
sea relate-video-events page0.json page1.json --offset 0 --limit 50
```

Provide 1–16 nonoverlapping v0.22 evidence pages from the same revision/settings. Pages may be unordered. Keep the same inputs while paging with next_offset (1–100 events per result). The audit rejects digest mismatches, duplicates and mixed revisions. Events reference the original evidence IDs and segment IDs. Relation target IDs may occur on another output page in the same batch.

## Measurements

Each sampled RGB difference marks pixels whose maximum channel difference is at least 25 (8-bit). Divide the padded frame into 4 × 4 equal-sized cells; mark cells with at least 10% changed pixels. Cell IDs 0–15 are row-major, top-left to bottom-right. Visual events require a scene candidate, at least one marked tile, or at least 5% changed pixels.

A follows_visual_change relation points to the previous visual candidate within two seconds in a contiguous run of complete submitted segments. For two non-scene candidates with nonempty grids, tile_jaccard is intersection size divided by union size (0–1). This measures spatial overlap, not motion direction or object identity. A near_audio_transition relation points to the nearest measured low-level flag change within 0.5 s; audio_minus_visual_s is signed. Audio bins are half-second windows with RMS threshold 0.01; no speech or sound classification. Ties prefer earlier audio events.

Missing segments, unavailable boundaries and incomplete modalities break continuity. Partial/failed segments are skipped and reported; a preceding boundary comparison is not used without the adjacent submitted segment. A batch is not a whole-video ledger. Audio/video timestamps are approximate. Global changes may be cuts, camera movement or lighting. No causal inference, native-frame completeness, authentication or semantic detection.

Use view_video_segment, read_video_frames and listen_video_segment (if supported) to confirm the actual observations. See [video coverage](video-coverage.md) and [video perception](video-perception.md).

Tests: [event relations](../tests/test_event_relations.py), [visual measurements](../tests/test_video_perception.py), [MCP](../tests/test_mcp.py).
