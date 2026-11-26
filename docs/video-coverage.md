# Video coverage audit

Use `analyze_target` or `sea analyze` to generate chronological video evidence pages. Keep segment_seconds and sample_fps consistent, follow next_cursor, and pass the original source_revision as expected_revision when requesting further pages.

Pass 1–16 full evidence envelopes to MCP `audit_video_coverage(evidence_pages)`, or use `sea audit-video-coverage page0.json page1.json`. Pages can be unordered, and page sizes may differ. No source file is read or stored by the audit.

The audit validates each record digest, source revision, engine version, sample rate, duration, segment plan, cursor and segment status. It rejects duplicate/overlapping segments. Results include:

- missing_ranges: half-open cursor intervals and their corresponding time ranges; request those pages next.
- incomplete_segments: partial/failed visual or audio measurements, or unavailable preceding boundary comparisons.
- all_segment_rows_submitted: every planned segment has a submitted row (even if decoding failed).
- all_sampled_measurements_reported_complete: no missing rows or incomplete reported measurements.

For more than 16 pages, audit batches separately and track the union of submitted ranges; a batch alone cannot establish full coverage for a long recording. For example, if one audit shows missing cursor range 0–12 and another shows 12–24, check both reports' submitted ranges and settings before combining them. The audit is not an incremental persistent ledger.

The digest verifies record consistency, not authenticity or source contents. A complete sampled timeline (1, 2 or 4 fps) is not exhaustive native-frame inspection or semantic understanding. Inspect ordered contact sheets and relevant native frames, and let the host interpret the evidence. Audio status not_present is allowed; this does not mean silence. See [video perception](video-perception.md) and [agent workflows](agent-workflows.md).

No new dependencies, model weights or persistent writes.
