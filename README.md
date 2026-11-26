<div align="center">

<img src="docs/assets/sea-hero.svg" alt="SEA — Sensory Extension for Agents. AI can think. SEA lets it perceive." width="100%">

# SEA — Sensory Extension for Agents

### Give your AI new senses.

**Give your AI measurable evidence from sound, video, images and recorded signals.**

[![GitHub stars](https://img.shields.io/github/stars/PCTestAdmin/SEA?style=flat-square&logo=github)](https://github.com/PCTestAdmin/SEA/stargazers)
[![Tests](https://github.com/PCTestAdmin/SEA/actions/workflows/test.yml/badge.svg)](https://github.com/PCTestAdmin/SEA/actions/workflows/test.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-22b8cf?style=flat-square)](LICENSE)
[![MCP](https://img.shields.io/badge/protocol-MCP-64748b?style=flat-square)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.17.0%20prototype-0891b2?style=flat-square)](pyproject.toml)

[Quick start](#quick-start) · [Showcase](#showcase) · [How it works](#how-it-works) · [Capabilities](#capabilities) · [Roadmap](#roadmap) · [FAQ](#faq)

</div>

---

Most AI assistants can reason about a description. But descriptions alone cannot tell them the frequency of a sound, when an image changed, or whether both events appeared in the same recording segment.

**SEA gives your agent access to the measurements themselves.** It is a local Model Context Protocol (MCP) extension, not another chatbot. Connect it to your existing assistant, select a recording, and ask a question.

> [!NOTE]
> SEA is an early open-source prototype. Audio, video, image-space and recorded sensor measurements plus optional pretrained object detection are implemented; live sensors, one-click desktop packages and semantic sound recognition are not yet available. Check the [live test results](https://github.com/PCTestAdmin/SEA/actions/workflows/test.yml) for platform verification.

## Quick start

**Requirements:** Python 3.10+, Git, FFmpeg and FFprobe available on PATH.

```bash
git clone https://github.com/PCTestAdmin/SEA.git
cd SEA
python -m pip install .
```

Create a dedicated media directory, close the client and run:

```bash
sea doctor
sea setup --client claude-desktop --media-root "/absolute/path/to/media"
```

Review the preview, then repeat with `--apply` to register SEA. Existing settings are preserved and the original config is backed up. Restart the client. Use `--client cursor` for Cursor, or `--config` for a compatible custom JSON configuration. Claude Desktop automatic path detection is limited to Windows and macOS.

Alternatively, install into a persistent isolated environment with `pipx install git+https://github.com/PCTestAdmin/SEA.git` (requires pipx and Git). SEA is not published on PyPI yet. See the [installation guide](docs/installation.md) for updates, troubleshooting and manual setup. No SEA account or API key is needed.

<details>
<summary><strong>Claude Desktop — configuration example</strong></summary>

Create a dedicated media folder and use the absolute path to the Python interpreter where SEA is installed. Merge this entry into your existing MCP configuration, replacing the example paths:

```json
{
  "mcpServers": {
    "sea": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "sea.server"],
      "env": {
        "SEA_MEDIA_ROOTS": "/absolute/path/to/media"
      }
    }
  }
}
```

Restart the client. See the [Windows configuration and troubleshooting guide](docs/installation.md). Other clients with local MCP support can use the same command and environment.

</details>

**Try asking your agent:**

```text
Analyze my recording with SEA. Find unusual changes in
sound or image, tell me when they occur, and show me
the measurements behind your answer.
```

## Showcase

<div align="center">
<img src="docs/assets/sea-demo.svg" width="100%" alt="Measured demo timeline: a 440 Hz tone from approximately 2 to 4 seconds and visual changes at the same boundaries.">
</div>

### Can an AI locate a sound and a visual change in the same video?

Our reproducible six-second fixture contains a black scene, a white scene with a 440 Hz tone, and a return to black and quiet. SEA analyzes the audio and video on a shared approximate timeline.

| Evidence | Recorded result |
| :--- | :--- |
| Dominant frequency during tone | 440 Hz |
| Tone detected | Approximately 2–4 s |
| Visual change bins | 2 |
| Sampled video frames | 24 |
| Overall digital RMS level | −18.09 dBFS |

These are historical measurements from the original MP4 synthetic test, not a live AI screenshot or a real-world benchmark. The illustration shows the reported tone and the known fixture scenes. Temporal overlap does not establish causation.

**Reproduce it yourself** — generate the fixture and ask your agent to inspect it:

```bash
python examples/make_demo.py /absolute/path/to/media/demo.avi
```

[Demo generator](examples/make_demo.py) · [Original MP4 JSON evidence](examples/demo-report.json) · [Test assertions](tests/test_engine.py)

### Acoustic evidence

Ask your agent to locate level changes, inspect frequency peaks and compare two equally long recording segments. SEA returns 100 ms level measurements, a time-frequency image and numeric differences rather than a guessed sound label.

```text
Use SEA to analyze this recording. Locate abrupt level changes,
inspect the spectrogram, and compare it with my reference recording.
Distinguish measured differences from possible explanations.
```

[Acoustic analysis guide](docs/acoustics.md) · [Reproducible acoustic tests](tests/test_acoustics.py)

### Investigate, don't just inspect

`investigate_media` brings the audio and visual engines together. It assigns evidence IDs, matches nearby point events and recommends timestamps for deeper frame inspection. The agent can then interpret and cross-check those observations.

```mermaid
flowchart LR
    A["Sense"] --> B["Measure"]
    B --> C["Correlate"]
    C --> D["Inspect evidence"]
    D --> E["Agent explains"]
```

```text
Investigate my video with SEA. Find changes in sound and image,
check whether they occur close together, then inspect the most
relevant frames. Explain the evidence and what remains unknown.
```

[Investigation guide](docs/investigation.md) · [Reproducible tests](tests/test_vision.py)

### Autonomous coarse-to-fine investigation

SEA can survey a recording, rank measured changes, revisit up to two promising windows and expose what it did not inspect. It operates within a bounded local decoding budget.

```text
Survey my recording with SEA. Investigate the strongest audio
and visual changes, inspect relevant frames, and tell me which
parts were not analyzed. Separate observations from hypotheses.
```

[Autonomous survey guide](docs/survey.md) · [Survey tests](tests/test_survey.py)

### Perception memory

Save an audio or sensor baseline explicitly and compare future measurements even after restarting the agent. Memory is disabled by default. Only numeric summaries and user-selected labels are saved; no raw recordings or source paths.

```text
Save this recording as my reference baseline.
Compare today's recording with that baseline and report
the measured differences without guessing the cause.
```

[Enable and use perception memory](docs/memory.md)

### Screenshot intelligence and agent skill

Read visible text with optional local Tesseract, locate changed screenshot regions, visualize pixel differences, or locate a known same-scale icon using template matching. These are not semantic object labels.

Install the official free Agent Skill separately:

```bash
npx skills add PCTestAdmin/SEA --skill sea-perception
```

Requires Node.js for the skill installer. The skill does not install the MCP server; follow Quick start first. [Skill source](skills/sea-perception/SKILL.md) · [Image guide](docs/images.md)

### Vision AI

Optional local pretrained object detection for common COCO classes in photos and individual video frames. Receive labeled bounding boxes, model scores, model provenance and a visual overlay. No model is downloaded automatically.

```text
Detect objects in my image with SEA, show the marked regions,
and explain which predictions need human verification.
```

[Enable Vision AI](docs/vision-ai.md) · [Detector tests](tests/test_detector.py)

### Open Vision

Find visual objects using short text descriptions instead of a fixed label catalog. Optional local OWLv2 returns ranked matches and normalized regions, with an annotated image for verification. English short descriptions work best. No automatic model downloads.

```text
Find a red cup, a computer mouse and a laptop in my photo.
Show the matching regions and explain uncertain predictions.
```

[Open Vision setup](docs/open-vision.md) · [Tests](tests/test_openvision.py)

### Object Tracking

Follow tentative COCO object tracks across sampled video frames. SEA links mutually unique, overlapping same-class detections, reports normalized movement, and breaks tracks when matching becomes ambiguous. Inspect an annotated contact sheet to verify the observations.

```text
Track the cat in my video using SEA. Show the sampled frames,
where the detected object moved, and where tracking was interrupted.
```

[Object Tracking guide](docs/tracking.md) · [Tests](tests/test_tracking.py)

### Verifiable evidence

Explicitly capture a supported measurement as a content-addressed JSON report with source SHA-256, analyzer parameters and engine version. Retrieve it in future sessions and check whether the source bytes still match.

[Evidence guide](docs/evidence.md)

### Micro-Motion Intelligence

Measure small image translations in a selected mechanical region, estimate dominant vibration frequency and inspect a displacement waveform. Optional reference-region subtraction compensates shared translation. No extra AI model needed.

```bash
python examples/make_motion_demo.py /absolute/path/to/media/motion.avi
```

Ask your agent to measure the region [0.1,0.1,0.9,0.9] at 24 fps for 4 seconds. The synthetic fixture has a known 3 Hz, 0.4 pixel oscillation. These are fixture inputs; see CI for validation. [Motion guide](docs/micro-motion.md)

### NASA JPL autoRIFT integration

Use the optional official autoRIFT 2.1.1 package to estimate local displacement between aligned image pairs. SEA reports raw upstream vectors and distinguishes matched, interpolated and missing points. It does not claim NASA endorsement or metric measurement. Native provider verification is a separate CI job.

[Installation and limitations](docs/displacement.md) · [Upstream NASA JPL project](https://github.com/nasa-jpl/autoRIFT)

### New in v0.17 — Universal Video Perception

**Your AI reasons. SEA provides the senses.** No extra AI model, API key or model weights are needed for the core video workflow. Navigate an entire MP4 in contiguous timed segments, inspect actual ordered frames, compare exact decoded frame ordinals, crop details, measure visual and audio changes, and return original audio excerpts as MCP WAV content.

```text
Use SEA to examine my entire MP4 from beginning to end.
Visit every timeline page and inspect ordered frame evidence.
Investigate important details, listen where supported, then explain
what happened and how events relate, citing the times and evidence.
```

[Universal Video Perception](docs/video-perception.md) · [Optional legacy model providers](docs/video-understanding.md)

## What could you use SEA for?

<table>
<tr>
<td width="50%" valign="top"><h3>Everyday recordings</h3><p>Find the time at which an unusual sound or visual change occurs in a recording. Inspect that segment instead of searching manually.</p></td>
<td width="50%" valign="top"><h3>Creators &amp; musicians</h3><p>Compare digital audio levels, find quiet sections and inspect the dominant frequency of a recorded tone.</p></td>
</tr>
<tr>
<td valign="top"><h3>Gamers &amp; streamers</h3><p>Locate large visual transitions or quiet audio intervals in a captured gameplay or stream clip.</p></td>
<td valign="top"><h3>Developers &amp; IT</h3><p>Investigate a screen recording of an issue, find relevant visual changes and request timestamp-selected frames.</p></td>
</tr>
</table>

These are suggested workflows using the current measurements, not claims that SEA recognizes every event or diagnoses its cause.

## How it works

```mermaid
flowchart LR
    A["Your AI assistant"] <-->|MCP stdio| B["SEA"]
    B --> C["Local media"]
    C --> D["Audio measurements"]
    C --> E["Video measurements"]
    D --> F["Shared timeline"]
    E --> F
    F --> B
```

SEA uses FFmpeg to decode selected local media and NumPy to calculate signal features. The agent receives structured results and can request a particular frame for closer inspection. It decides how to interpret the evidence; SEA reports measurements and their limitations.

## Capabilities

| Tool | What your agent receives |
| :--- | :--- |
| `inspect_media` | Duration, stream metadata and codecs |
| `sense_media` | Audio levels, dominant frequency, quiet intervals and video differences on a half-second timeline |
| `view_frame` | A PNG near a requested video timestamp |
| `sense_audio` | Spectral peaks, band power, 100 ms levels and threshold events |
| `audio_spectrogram` | Time-frequency PNG for visual investigation |
| `compare_recordings` | Numeric differences between equally long audio segments |
| `sense_video` | Sampled visual activity, histogram shifts, change regions and static intervals |
| `investigate_media` | Evidence-indexed multimodal report, temporal matches and frame follow-ups |
| `inspect_spatial` | Image-space grid, regional color and contrast measurements |
| `inspect_region` | PNG crop of a selected normalized image region |
| `sense_signals` | Numeric sensor CSV statistics, change events and correlations |
| `investigate_recording` | Bounded multi-window survey, ranked candidates, targeted refinement and coverage gaps |
| `remember_audio` | Explicitly save numeric audio baseline |
| `remember_signals` | Explicitly save numeric sensor baseline |
| `list_perception_memory` | List saved baseline IDs and labels |
| `recall_perception` | Retrieve historical evidence |
| `compare_perception` | Compare compatible saved summaries |
| `forget_perception` | Explicitly delete one saved record |
| `read_image_text` | OCR words, confidence and normalized boxes |
| `compare_images` | Measured screenshot differences and changed regions |
| `view_image_difference` | PNG overlay highlighting changed pixels |
| `find_image_template` | Single-scale grayscale template localization |
| `guided_workflows` | Read-only agent workflow discovery |
| `vision_status` | Optional detector readiness and checkpoint provenance |
| `detect_objects` | COCO object predictions, scores and bounding boxes |
| `view_detections` | Annotated image of model predictions |
| `open_vision_status` | Local OWLv2 provider readiness |
| `find_objects_by_text` | Text-conditioned object localization |
| `view_text_matches` | Annotated text-search results |
| `track_objects` | Tentative sampled object tracks and normalized movement |
| `view_object_tracks` | Annotated sampled-frame contact sheet |
| `capture_evidence` | Run and explicitly save a supported measurement report |
| `list_evidence` | List stored reports |
| `recall_evidence` | Retrieve and export a digest-checked JSON envelope |
| `verify_evidence` | Compare source bytes and stored report digest |
| `delete_evidence` | Explicitly delete one report |
| `measure_micro_motion` | Small image displacement and dominant vibration frequency estimates |
| `view_motion_waveform` | Plot measured displacement with invalid-sample gaps |
| `autorift_status` | Optional pinned autoRIFT provider discovery |
| `measure_displacement` | Native autoRIFT grid vectors with missing/interpolated masks |
| `view_displacement_field` | Visualize raw displacement field |
| `video_understanding_status` | Discover optional video and speech providers |
| `plan_video_analysis` | Contiguous whole-file segment plan, paginated |
| `analyze_video_page` | Local clip descriptions and timed speech transcripts |
| `view_video_segment` | Timestamped ordered frame sheet for host vision |
| `scan_video_timeline` | Model-free contiguous visual/audio measurements and scene candidates |
| `read_video_frames` | Consecutive decoded frame ordinals and contact sheet |
| `view_video_frame_region` | Crop an exact decoded frame ordinal |
| `compare_video_frames` | Compare exact frame ordinals and show changes |
| `listen_video_segment` | Bounded WAV audio content for compatible hosts |

<details>
<summary><strong>Supported media and measurement limits</strong></summary>

| Input / parameter | Current support |
| :--- | :--- |
| Audio | WAV, MP3, FLAC, M4A, OGG, OPUS |
| Video | MP4, MOV, MKV, WebM, AVI |
| Still images | PNG, JPEG (spatial tools only) |
| Sensor logs | Numeric UTF-8 CSV, up to 2 MiB / 20,000 rows |
| Maximum file size | 2 GiB |
| Analysis window | 0.25–120 s visual, 0.25–30 s acoustic/investigation, 0.25–60 s combined legacy tool |
| Audio sampling | First audio stream, mono, 16 kHz |
| Video sampling | First video stream, grayscale, 160 × 90, 4 fps |
| Timeline | Approximate half-second bins |
| Survey span | Up to 30 min, sampled (not exhaustive) |

Decoder support depends on the FFmpeg installation. Frame differences are not object tracking or proof of movement. Audio levels are not calibrated physical loudness or proof of clipping. A dominant frequency does not identify a sound source. Exact audiovisual sync, speech transcription and semantic music analysis are outside the current scope.

</details>

## Privacy by design

- Local processing of explicitly configured media folders.
- No SEA cloud account, remote media URL input, microphone capture or background service.
- Perception memory is disabled unless SEA_MEMORY_DIR is configured; save and delete operations require explicit user approval.
- No uploads initiated by SEA. Tool results, including requested frames, are returned to your MCP host and may be transmitted to its model provider.
- Folder restrictions are not an operating-system sandbox. Use trusted media in a dedicated directory and keep FFmpeg updated.

See [installation and usage details](docs/installation.md).

## Roadmap

- [x] Local audio and video analysis engine
- [x] Structured MCP tool implementation
- [x] Reproducible audiovisual example
- [x] Preview-first client registration, backups and prerequisite checks
- [ ] Verified client integration and cross-platform installation
- [x] Official Agent Skill and guided workflow discovery
- [x] Screenshot OCR, pixel differences and template localization
- [x] Optional local COCO object detector
- [x] Optional text-conditioned OWLv2 detection
- [x] Sampled COCO object tracking and visual contact sheets
- [x] Opt-in content-addressed evidence reports for selected analyzers
- [x] Experimental small-motion measurement and waveform
- [x] Optional autoRIFT adapter (native verification tracked in CI)
- [x] Model-free whole-file timeline, frame navigation, audio content and visual evidence
- [x] Optional legacy semantic provider interfaces (model verification pending)
- [ ] One-click desktop extension / package distribution
- [ ] More precise timestamp alignment and labeled benchmarks
- [x] Spectrograms, threshold-based audio event localization and recording comparisons
- [x] Evidence-indexed multimodal investigation and sampled visual change regions
- [x] Image-space spatial analysis and region inspection
- [x] Numeric sensor-log analysis and paired-channel correlations
- [x] Budgeted coarse-to-fine recording investigation
- [ ] Physical depth and live sensor integration
- [x] Opt-in persistent audio and sensor baseline history

The long-term goal is a modular perception layer for AI agents. We prioritize features that yield observable, testable information rather than adding tools for their own sake.

## FAQ

<details>
<summary><strong>Is SEA an AI model?</strong></summary>

No. SEA adds media analysis tools to an existing assistant. It does not replace the model.

</details>

<details>
<summary><strong>Can I use it with Claude, Cursor or Codex?</strong></summary>

SEA exposes a local MCP stdio server. SEA provides configuration helpers for Claude Desktop and Cursor; compatible clients can also be configured manually. The current prototype does not claim verified compatibility with every client or platform; see the [setup guide](docs/installation.md).

</details>

<details>
<summary><strong>Can SEA understand music or diagnose an unusual noise?</strong></summary>

Not by itself. It can measure frequencies, levels and timestamps; interpreting a complex sound requires further evidence. No automatic source identification or machine diagnosis is implemented.

</details>

<details>
<summary><strong>Can I analyze files without an AI assistant?</strong></summary>

Yes. The same engine has a diagnostic CLI. See [command-line usage](docs/installation.md#command-line-usage).

</details>

<details>
<summary><strong>Does SEA need internet access?</strong></summary>

The media engine needs no network connection. Installing dependencies may require internet access, and your chosen AI host may use a cloud model.

</details>

## Documentation

| Guide | Content |
| :--- | :--- |
| [Installation & troubleshooting](docs/installation.md) | Prerequisites, platform configuration, CLI |
| [Universal Video Perception](docs/video-perception.md) | Model-free timeline, exact frame ordinals, audio and visual evidence |
| [Optional model providers](docs/video-understanding.md) | Legacy opt-in descriptions and speech |
| [Precision Displacement](docs/displacement.md) | Optional NASA JPL autoRIFT provider |
| [Micro-Motion](docs/micro-motion.md) | Mechanical motion measurement and reproducible fixture |
| [Evidence system](docs/evidence.md) | Content-addressed reports and source verification |
| [Object Tracking](docs/tracking.md) | Sampled tracks, ambiguity handling and image-space movement |
| [Open Vision](docs/open-vision.md) | Optional text-conditioned detection |
| [Vision AI](docs/vision-ai.md) | Optional pretrained object detection and setup |
| [Screenshot intelligence](docs/images.md) | OCR, visual comparison and templates |
| [Agent Skill](skills/sea-perception/SKILL.md) | Agent instructions and workflows |
| [Perception memory](docs/memory.md) | Opt-in SQLite baseline history and comparison |
| [Autonomous survey](docs/survey.md) | Sampling plan, ranking, refinement and coverage |
| [Sensor signals](docs/signals.md) | CSV schema, thresholds and paired-channel analysis |
| [Spatial analysis](docs/spatial.md) | Image grids, normalized regions and crops |
| [Multimodal investigation](docs/investigation.md) | Visual measurements, correlation and follow-up workflow |
| [Acoustic analysis](docs/acoustics.md) | Spectrograms, measurements, comparisons and limitations |
| [Example evidence](examples/demo-report.json) | Structured demo output |
| [Development tests](tests/) | Engine and MCP integration tests |
| [License](LICENSE) | MIT |

## Contributing

SEA is at the beginning of its journey. If you find an interesting use case, [share it in an issue](https://github.com/PCTestAdmin/SEA/issues). Include the kind of media, the question you asked and what the agent could or could not determine. Avoid posting private recordings.

Bug reports, reproducible benchmarks, new analysis modules and documentation contributions are welcome.

<div align="center">

**If SEA gives your agent a useful new capability, consider [starring the project](https://github.com/PCTestAdmin/SEA).**

MIT licensed · Built in the open

</div>
