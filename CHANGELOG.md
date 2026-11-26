# Changelog

## 0.18.0

- Fix autoRIFT small-grid configuration: use coarse search stride 1 rather than the large-scene default of 4, preserving upstream consistency filtering and the original native accuracy assertions. Add adapter configuration regression coverage.

- Opt-in reusable SQLite temporal index of decoded frame ordinals, best-effort PTS ticks, relative timestamps and keyframe flags.
- Indexed nearest-time and ordinal lookup, paginated metadata and searchable host-authored observation notes.
- Explicit save/delete consent, source revision checks, bounded storage and no raw frames or model inference.
- Four test cases and MCP round-trip coverage; prior autoRIFT native test remains unresolved.

## 0.17.0

- Restore model-free perception as the primary video workflow; existing optional model adapters remain for compatibility.
- Contiguous timeline measurements with candidate scene changes and cross-page boundary comparisons.
- Exact decoded frame ordinals, ordered sheets, regional crops and frame difference overlays.
- Original audio excerpts as MCP WAV content for compatible hosts.
- Five core tests and real MCP round-trip coverage. No new required dependencies or model weights.

## 0.16.0

- Chronological whole-file video segment planning and paginated analysis, with explicit failed segment states and revision checks.
- Optional local Qwen2.5-VL clip descriptions and Faster-Whisper speech transcripts.
- Timestamped visual contact sheets usable without additional model weights.
- Four core tests, optional real model smoke test and MCP coverage; semantic model quality not yet verified.
- Skill instructs hosts to visit every segment and synthesize evidence across time.

## 0.15.0

- Optional native NASA JPL autoRIFT 2.1.1 integration in a bounded subprocess.
- Three MCP tools for discovery, grid displacement and vector visualization.
- Direct/interpolated/missing masks, fixed chip size and bounded image sampling.
- Four core tests and a separate native-provider synthetic shift test. No upstream code bundled.

## 0.14.0

- Fix Windows evidence test cleanup: explicitly close SQLite connections after test transactions.

- Experimental small mechanical image-translation estimates, optional reference subtraction and dominant vibration frequency.
- Numeric and waveform MCP tools, synthetic subpixel-motion AVI fixture and five tests including decoded video.
- No new dependencies or third-party research code. Not full motion magnification, dense optical flow or calibrated physical measurements.

## 0.13.0

- Opt-in content-addressed JSON measurement reports with source SHA-256 and analyzer provenance.
- Five evidence tools, bounded local storage and explicit save/delete confirmation.
- Five unit tests and MCP integration coverage. Hash verification is not authentication.

## 0.12.0

- Sampled COCO object tracking with conservative adjacent-frame association and explicit gaps.
- Normalized center displacement and sampled path length; annotated contact sheets.
- Load one optional CPU detector per tracking invocation instead of per sample.
- Five core tracking tests, a real pretrained video smoke test and MCP integration coverage.
- Updated official skill, workflow catalog and documentation.

## 0.11.0

- Fix Open Vision preprocessing by declaring SciPy, checking its availability and selecting the slow processor explicitly. The subsequent pretrained Open Vision and cross-platform checks passed.

- Optional local OWLv2 text-conditioned object localization, annotated matches and readiness checks.
- Bounded text queries, per-label overlap suppression, weight digest and explicit limitations.
- Core and MCP tests; separate pretrained OWLv2 workflow on relevant main-branch changes.
- Fix COCO fixture TLS failure using pinned Transformers test image; TLS verification remains enabled.

## 0.10.0

- Optional offline Torchvision SSDLite COCO detector with explicit local checkpoint and verified official hash prefix.
- Three MCP tools: readiness, object predictions and annotated detections.
- Detector provenance, normalized bounding boxes and bounded outputs.
- Unit tests, expanded MCP checks and separate pretrained inference CI lane.
- Updated official skill and workflow discovery. No automatic model downloads.

## 0.9.0

- Official free Agent Skill and read-only guided workflows.
- Screenshot OCR with optional Tesseract, visual diff overlays and same-scale template matching.
- Pillow still-image backend, AVI support and pure-Python test fixture; Windows CI selects actual FFmpeg binaries instead of Chocolatey shims.
- Five screenshot tests and expanded MCP verification.

## 0.8.0

- Opt-in local SQLite history for measured audio and sensor baselines.
- Six MCP tools for saving, listing, recalling, comparing and deleting measurement summaries.
- Bounded storage (100 records), no raw media or source paths, no automatic capture.
- Five memory tests and expanded protocol checks.
- Updated SPDX license metadata.

## 0.7.0

- CI hotfix: replace hanging lavfi fixture generation with finite raw YUV frames, single-thread encoding and bounded subprocesses. Windows verification is pending.

- Bounded coarse-to-fine recording survey: up to five six-second windows, up to two four-second refinements.
- Ranked audiovisual evidence candidates, explicit requested-range coverage gaps and visible failures.
- Five survey tests and additional MCP integration coverage.
- No unrestricted autonomous actions, semantic event claims or exhaustive coverage promises.

## 0.6.0

- Numeric CSV sensor-log analysis with explicit seconds and channel selection.
- Per-channel summaries, bounded adjacent-change evidence, optional thresholds and same-row Pearson correlation.
- Four signal tests and an additional MCP round trip; no live device access.

## 0.5.0

- Image-space spatial grids, regional color/contrast metrics and normalized region crops.
- PNG/JPEG input for spatial tools; video frame support.
- Spatial unit and MCP integration tests; no physical distance or depth inference.

## 0.4.0

- Sampled visual activity, large global changes, histogram shifts, normalized change regions and low-change intervals.
- Evidence-indexed multimodal investigation, nearest temporal matches and ranked frame follow-ups.
- Visual scanning up to 120 seconds and investigation up to 30 seconds per call.
- Six vision/investigation tests and expanded MCP integration checks.
- Existing tool contracts preserved.

## 0.3.0

- Acoustic spectral peaks, band fractions and 100 ms threshold-based level events.
- Spectrogram PNG tool and equal-duration recording comparison.
- Six acoustic unit tests and expanded MCP integration test.
- Fix macOS setup-test false positive caused by the /private temporary path.

## 0.2.0

- Preview-first `sea setup` for Claude Desktop and Cursor or a custom JSON path.
- Explicit apply and replace controls, preservation of unrelated settings and exact backups.
- `sea doctor` and `sea --version` commands.
- Seven setup tests and updated installation documentation.
- Existing audiovisual engine and MCP tool contracts unchanged.

## 0.1.0

- Initial local audiovisual measurements, shared timeline and frame retrieval.
