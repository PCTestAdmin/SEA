# Low-token video analysis

Use compact_video_overview first for most questions about local video. It scans and compresses within SEA; raw comparisons and audio bins are not sent to the host. No storage or new dependencies. Use authorized SEA_MEDIA_ROOTS as usual.

CLI:

```bash
sea compact-video /absolute/path/video.mp4 --segment-seconds 12 --max-segments 3 --sample-fps 4 --output-budget-bytes 6000
```

Follow next_cursor with identical segment_seconds and sample_fps and the returned source_revision as expected_revision. Null means the declared end was reached, not that every modality succeeded. Each call returns at most six segments; the output budget can end a page earlier without skipping any segment.

## Compact schema

Each row i starts at i*segment_seconds and ends at end_s. v/a/boundary are the original visual/audio/boundary statuses. samples/expected are counts. cuts and review contain integer sample ticks relative to the segment start: divide by fps and add the start time. peak is [tick, changed pixel fraction] for the largest measured non-cut visual change. All cut candidates in the returned segment are retained. Review points are hints, not exhaustive visual inspection.

observed_ms and low_ms are merged relative millisecond ranges. The complement of observed_ms within a measured/partial segment is unknown, never silence. a=not_present explicitly means no audio stream. freq_hz lists up to three dominant-frequency candidates ranked by observed non-low bin duration. It does not identify the sound. Rounding is to milliseconds.

## Resource and quality controls

- 4 fps is the default; 1 or 2 fps reduces sampled frames and comparisons but may miss brief events. This is not exact native-frame analysis.
- The hard budget counts ASCII JSON bytes, excluding protocol framing or CLI newline; no model-specific token count is promised.
- raw_rows_json_bytes reports the equivalent compact-serialized raw measurement array for the returned rows. Compare it against the actual response text length, not the file size or model usage.
- MCP returns one TextContent JSON string, not both text and structured copies.
- Use analyze_target with the same revision/settings and cursor i for full detail, view_frame/view_video_segment for visual verification, or listen_video_segment for compatible audio hosts. Do not claim uninspected content was understood. For complete semantic analysis, the host may need many additional frames.
- Budget limits response size, not decoder runtime. Up to three segments may have been scanned locally before a budget boundary; an unreturned segment will be revisited at the next cursor. A bounded process-local cache can reuse complete segments for five minutes (128 entries, 256 KiB serialized payloads); disable with SEA_SCAN_CACHE=off. Incomplete segments are retried. No persistent cache.

CI compares the actual serialized compact response on a controlled real AVI fixture against its raw rows and exercises dense candidate pagination. This is not a real-world model token benchmark.

## Lean MCP tool discovery

Set SEA_MCP_PROFILE=video before starting SEA or use `sea setup --profile video` with the normal client/media-root arguments. The nine registered tools cover compact scanning, metadata, selected frames, audio and full detail. Full remains default; optional models, indexing and persistent writes are unavailable in the video profile. Restart the client after configuration changes. Tool-schema JSON size and model tokens are distinct.
