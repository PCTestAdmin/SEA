# Changelog

## 0.24.0

- Add model-free candidate scene navigation over audited portable video evidence. Preserve unknown spans, merge observed boundaries, retain audio independently of visual failures, expose low-level audio and dominant-frequency bin overlap, and link representative samples to segment and evidence IDs.
- Expose summarize_video_scenes over MCP, CLI and agent workflows; include real AVI, malformed evidence, partial modality, boundary, pagination and MCP contract tests. No added runtime dependencies or semantic inference. Cross-platform CI must verify this release.

## 0.23.3

- Fix inconsistent audio coverage and event-relation boundaries: measured segments already allowed up to 30 ms of decoder shortfall, but relation detection required contiguous bins within about 1 ms. Preserve observed level changes across joined measured segments only within the existing coverage tolerance, explicitly expose the unobserved gap on the event and its visual link, and never fill missing samples.
- Add boundary regression tests for 16, 30, 31 and 80 ms gaps and include segment diagnostics in the real MP4 relation assertion. Keep the original visual/audio coverage and event assertions. The macOS v0.23.2 failure had complete reported coverage and both scene cuts but lacked one audio relation; the exact bin gap was not printed, so this fix addresses an identified consistency issue and remains subject to CI verification.

## 0.23.2

- Freeze a small, SHA-256-verified MPEG-4/AAC smoke fixture instead of encoding it on every CI runner. The file contains exactly six seconds of video and 48 kHz mono audio; tests still decode real MP4 and require both scene changes, complete sampled audio/video coverage and cross-modal transitions.
- Keep the previous strict assertions and add a fixture integrity check. FFmpeg 9.1 on Windows previously timed out during fixture encoding; FFmpeg 9.0.2 on macOS returned 32 ms less audio per segment from the previous fixture. The new fixture was independently decoded with FFmpeg 7.1.5; the precise FFmpeg 9 behavior and cross-platform CI outcome remain to be verified.

## 0.23.1

- Address the v0.23.0 Windows MP4 fixture encoding timeout and macOS missing scene-candidate failure by replacing AVI transcoding with bounded direct RGB/WAV encoding (MPEG-4/AAC), explicit stream mapping, single-threaded encoders, intra frames and disabled stdin.
- Strengthen MP4 assertions to require both complete segment measurements, exact sample counts, boundary coverage, both known scene changes and nearby audio transitions. Failures now include segment diagnostics; no tests skipped or thresholds relaxed.
- Update fixture documentation. The raw-input encoding and segment decoding were checked locally with FFmpeg 7.1.5; cross-platform CI and the exact cause of the prior macOS missing candidates remain to be verified.

## 0.23.0

- Add offline paired Reality Benchmark CLI: freeze hashed MP4 suites, generate answer-free packets and run templates, score matched model runs with accuracy, gains/regressions, abstentions, per-category and real/synthetic breakdowns and runtime.
- Document controlled host comparison and real-world footage preparation, including external Perception Test data guidance. No third-party clips or measured model scores bundled.
- Add actual MP4 decoding smoke test and deterministic scorer/CLI regression coverage. No new mandatory dependencies.
- All four v0.22 CI workflows passed. v0.23 CI not yet verified.

## 0.22.0

- Add 4 × 4 changed-tile measurements to sampled visual comparisons and model-free event relations across contiguous complete evidence pages.
- New MCP relate_video_events and CLI relate-video-events with paginated events, evidence references, visual sequence, tile overlap and nearby audio-level transitions.
- Missing or incomplete segments break continuity. No identity, semantic or causal claims. No new dependencies.
- Fix stale hardcoded doctor version assertion: use the package version. The v0.21 main CI passed its evidence parity and coverage tests but failed the old version assertion; all three optional smoke workflows passed.
- Add synthetic and real fixture regression tests, MCP integration, README and skill updates. v0.22 CI not yet verified.

## 0.21.0

- Normalize time arguments before shared analysis and hashing to fix CLI/Python/MCP evidence parity (integer versus floating-point representations).
- Add model-free video coverage auditing via MCP and CLI: validate portable evidence, detect missing ranges, reject duplicate segments and mixed settings, distinguish incomplete modalities and unavailable boundaries.
- Update the README, official skill, workflow guidance and regression tests. No new dependencies or persistent writes.
- Cross-platform CI for this version is not yet verified.

## 0.20.0

- Shared target-aware model-free analysis for MCP and the SEA CLI, with portable digest-identified evidence and bounded inline projections.
- Four native MCP prompts and shared guided workflow renderer.
- Unified CLI analyze, inspect-evidence and guided-workflows commands; older entry points retained.
- No new mandatory dependencies, model weights or persistent writes. Tests cover CLI/MCP parity, evidence integrity, paging and prompt discovery.
- All v0.19 platform and optional native/model CI checks passed.

## 0.19.0

- Model-free reusable visual fingerprints over sampled decoded frame ordinals, search by local image or indexed frame.
- Paginated same-scale template matching with approximate times and normalized sample coordinates.
- Explicit opt-in storage, source revision checks, selective descriptor deletion and cascading temporal index deletion.
- Four core tests and MCP integration coverage. No new dependencies.
- Previous autoRIFT small-grid hotfix passed its native smoke test.

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
