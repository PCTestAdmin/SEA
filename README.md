# SEA — Sensory Extension for Agents

**AI can think. SEA lets it perceive.**

SEA is a local MCP server that gives AI agents measurable audio and video evidence on a shared timeline, rather than only a transcript or a collection of screenshots.

> Early prototype (0.1.0). Local Linux engine tests pass; MCP transport and other operating systems require the integration tests to pass before a stable release.

## What it does

- `inspect_media`: stream metadata and duration.
- `sense_media`: digital audio level, dominant spectral frequency, quiet intervals and sampled visual changes in the same half-second timeline.
- `view_frame`: a timestamp-selected PNG returned to the MCP client as image content.

Use it to locate an unusual sound in a recording, identify when a screen changes in a tutorial, or compare audio levels across segments. SEA measures signals; it does not identify the cause of a noise, perform speech recognition, diagnose machines, track objects, or infer exact audiovisual synchronization. A vision-capable host can interpret returned frames.

## Reproducible demo

The synthetic six-second sample contains a quiet black scene, a white scene with a 440 Hz tone from about 2 to 4 seconds, then silence and black again. Generate it yourself:

```sh
python examples/make_demo.py /absolute/path/to/media/demo.mp4
```

Ask your MCP host: **Analyze demo.mp4 using SEA. Tell me when the tone starts, when the visual scene changes, and what evidence supports your conclusion. Inspect a frame near 2.5 seconds.**

See [actual local demo output](examples/demo-report.json). This is a generated fixture, not a real-world benchmark. See tests/ for assertions.

## Installation

Requirements: Python 3.10+, FFmpeg and FFprobe on PATH. Install FFmpeg from a trusted package manager, e.g. winget install Gyan.FFmpeg (Windows), brew install ffmpeg (macOS), or sudo apt install ffmpeg (Debian/Ubuntu). These are optional manual installation commands, not executed by SEA. Restart the client if PATH changes.

From an extracted source folder:

```sh
python -m pip install .
```

For Claude Desktop, edit the local MCP configuration (Settings > Developer > Edit Config where available) and restart Claude. Use an absolute path to the Python interpreter where SEA was installed. Choose a dedicated media folder, **not your home directory**. Example Windows configuration (replace both paths):

```json
{
  "mcpServers": {
    "sea": {
      "command": "C:\\Users\\YOU\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "args": ["-m", "sea.server"],
      "env": {"SEA_MEDIA_ROOTS": "C:\\Users\\YOU\\SEA-Media"}
    }
  }
}
```

Linux/macOS example:

```json
{
  "mcpServers": {
    "sea": {
      "command": "/absolute/path/to/python3",
      "args": ["-m", "sea.server"],
      "env": {"SEA_MEDIA_ROOTS": "/absolute/path/to/media"}
    }
  }
}
```

Other MCP clients can use the same stdio command and environment. No hosted API or API key is needed for the server. A .mcpb one-click extension and public package are planned, not included in this prototype.

### Core diagnostics (without MCP)

With numpy installed and FFmpeg available, from the source folder:

```sh
SEA_MEDIA_ROOTS=/absolute/path/to/media python -m sea.cli /absolute/path/to/media/demo.mp4 --duration 6
```

PowerShell: set $env:SEA_MEDIA_ROOTS = 'C:\Users\YOU\SEA-Media' first, then run python -m sea.cli C:\Users\YOU\SEA-Media\demo.mp4 --duration 6.

## Privacy and limitations

- No listening network service, cloud API, external model downloads, microphone access, URL input or arbitrary command execution. SEA reads selected local files and uses FFmpeg with fixed arguments. Results (including frames) go to the MCP host, which may send them to its model provider. Local analysis is not a promise of end-to-end local AI processing.
- Set SEA_MEDIA_ROOTS to existing directories separated by the OS path separator (; on Windows, : on Unix). Resolved paths outside these directories are rejected. Use a dedicated folder with trusted media. This is not an OS sandbox; avoid hostile media, concurrent path replacement, network mounts, or shared writable directories. Keep FFmpeg patched.
- Only the first audio and video streams are analyzed. Audio is downmixed to mono at 16 kHz; visual differences use 160×90 grayscale samples at 4 fps. The output is approximate; no exact source PTS alignment. Max file size 2 GiB; max segment 60 seconds; decoder timeout 45 seconds per operation. A fixed threshold marks low-level audio (<−40 dBFS) and larger visual changes (normalized mean pixel difference ≥0.12). These are heuristics, not semantic detection.
- The null audio level means digital silence if audio is observed, otherwise unavailable; no proof of clipping, calibrated loudness, causal relationship or human-equivalent sensory perception.

## Development

```sh
python -m pip install .
python -m unittest discover -s tests -v
```

CI is configured for Windows, macOS and Linux, including an actual MCP stdio client handshake and tool call. The SDK-dependent test is skipped if the SDK is unavailable locally; CI explicitly imports the SDK before tests.

## Roadmap

1. Validate MCP installation across hosts, publish an installable extension.
2. Source-timestamp alignment and more rigorous signal analysis, with labeled benchmark recordings.
3. Optional spectrograms, event localization and controlled comparison of recordings.
4. Additional sensors only when there is a measurable user benefit.

SEA does not claim to be the first media MCP. The experiment is a shared, evidence-oriented timeline across modalities. Contributions and reproducible benchmarks are welcome.

MIT licensed.
