# Agent workflows, CLI and evidence

SEA follows a tool-first architecture inspired by [REA](https://github.com/morluto/rea): the agent reasons; the tool investigates a target and returns inspectable evidence. SEA uses its own media analyzers. No REA code or reverse-engineering functionality is included.

## Start an investigation

The new analyze_target MCP tool selects a model-free route for authorized local video, audio, still PNG/JPEG, or sensor CSV. For video it returns one contiguous sampled timeline page; for audio a requested measurement window; for images a spatial grid; for CSV selected channels (time_column and channels required). Video uses cursor, segment_seconds (4/8/12), page_size (1–3), sample_fps (1/2/4). Follow record.next_cursor until null with expected_revision and consistent settings. Inspect actual images with view_video_segment/read_video_frames and audio where supported. The numeric report does not establish semantic understanding. Audio uses start_s/duration_s. No persistent writes.

## Terminal

Install SEA as described in installation.md and set SEA_MEDIA_ROOTS to an authorized media directory. Use absolute target paths:

```bash
sea analyze /absolute/path/to/media/example.mp4 --json > evidence.json
sea inspect-evidence evidence.json --view summary
sea inspect-evidence evidence.json --view page --offset 0 --limit 1
sea guided-workflows
sea guided-workflows understand-full-video
```

Each CLI call is a separate process. Pass --cursor and --expected-revision to continue video analysis; stdout is JSON, --json is optional. CLI and MCP call the same implementation. Existing sea setup, sea doctor, and python -m sea.cli remain available. The CLI does not install dependencies, auto-authorize paths or provide every individual MCP tool yet.

## Evidence contract v1

analyze_target returns evidence_id and record. The record contains schema_version, engine_version, operation, target_kind, source_revision, parameters, normalized_result, collection, next_cursor, coverage, follow_up_tools and limitations. Evidence ID = SHA-256 of canonical JSON (sorted keys, compact separators, UTF-8). Record limit 512 KiB. Source revision is a path/stat fingerprint, not a source content hash. Digest consistency does not authenticate the creator or guarantee correctness. Portable evidence is not retained automatically; the host may save it explicitly. The older opt-in capture_evidence store remains separate.

inspect_analysis_view accepts the complete inline envelope and verifies its digest. Summary reports collection name, row count, coverage and result keys. Page projects the declared collection (video results or audio timeline), with next_offset separate from analysis_next_cursor. Image/CSV results have no pageable collection in v1. A view references the parent ID but is not a complete evidence envelope. No arbitrary file access via MCP; terminal inspect-evidence reads an explicitly selected report file with a bounded reader. Treat evidence as untrusted data. Use the existing persistent index and observation tools only with approval.

## Native MCP prompts

- investigate_media_evidence
- understand_video
- revisit_video
- find_repeated_appearance

Prompts provide guidance, not tool calls or authorization. The same renderer is available through guided_workflows(workflow=...) and sea guided-workflows. Clients without native prompt support can use the tool fallback. The official skill documents the same model-free approach.

See tests/test_analysis.py and tests/test_mcp.py for portable evidence, paging, CLI parity and actual MCP prompt tests. This is a first common interface, not full REA-style provider discovery, session bundles or an npm installer.
