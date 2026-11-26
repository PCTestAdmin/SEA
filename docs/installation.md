# Installation & usage

[Back to SEA](../README.md)

## Prerequisites

- Python 3.10 or newer, Git, FFmpeg and FFprobe on PATH.
- Windows, macOS and Linux are CI targets; see [test runs](https://github.com/PCTestAdmin/SEA/actions/workflows/test.yml) for current status.
- Install FFmpeg using a trusted source or package manager. Examples: `winget install Gyan.FFmpeg` (Windows), `brew install ffmpeg` (macOS), `sudo apt install ffmpeg` (Debian/Ubuntu). Restart the client if PATH changes.

```sh
git clone https://github.com/PCTestAdmin/SEA.git
cd SEA
python -m pip install .
ffmpeg -version
ffprobe -version
python -c "import sys; print(sys.executable)"
```

The last command prints the interpreter path to use in your MCP configuration. A virtual environment is recommended.

## Guided setup (v0.2+)

Install SEA into a persistent environment (not a temporary package runner). You can also use `pipx install git+https://github.com/PCTestAdmin/SEA.git` if pipx and Git are installed.

Create your dedicated media directory first, then close the MCP client and run:

```bash
sea doctor
sea setup --client claude-desktop --media-root "/absolute/path/to/media"
sea setup --client claude-desktop --media-root "/absolute/path/to/media" --apply
```

The first setup command is a preview only. Review its output before applying. Windows users can substitute a quoted path such as `C:\Users\YOU\SEA-Media`. For Cursor use `--client cursor` (global MCP config). Claude Desktop default paths are supported on Windows and macOS; elsewhere use `--config /absolute/path/to/config.json` with a compatible JSON schema.

Existing unrelated settings and MCP entries are preserved semantically; the JSON formatting may change. The exact previous bytes are saved in a uniquely named .bak file next to the config before replacement. Backups can contain existing credentials; keep them private. Invalid JSON, duplicate keys, symlink config files and differing SEA entries are refused by default. `--replace` explicitly authorizes replacing only the SEA entry. Close the client during setup; concurrent edits are not supported. Setup does not install FFmpeg or start the client. Restart your client afterward. `sea doctor` only checks prerequisite discoverability, not a live MCP connection.

To undo registration, close the client and remove only the sea entry from mcpServers; alternatively restore the backup if no later configuration edits need preserving. Keep a copy of the current config first. To update a pipx install, use `pipx upgrade sea-perception-mcp`; for a source install, pull the latest code and reinstall using the same interpreter. Repeat setup if its interpreter path changes.

## Manual connection to an MCP client

Create an existing dedicated folder for media you want the agent to access. Set `SEA_MEDIA_ROOTS` to that folder. Multiple roots can be separated using the OS path separator (semicolon on Windows, colon on Unix). Do not configure your entire home directory.

In Claude Desktop, open the local MCP config (Settings > Developer > Edit Config where available). Merge the entry rather than replacing any existing servers. Substitute the actual absolute paths.

### Windows example

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

### macOS / Linux example

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

Restart the MCP client and verify that SEA exposes 56 tools, including [Temporal Index](temporal-index.md), [Universal Video Perception](video-perception.md), [Video Understanding](video-understanding.md), [optional autoRIFT](displacement.md), [Micro-Motion](micro-motion.md), [evidence reports](evidence.md), [Object Tracking](tracking.md) and optional Vision AI and [Open Vision](open-vision.md). See [model setup](vision-ai.md). Memory operations require optional setup described in [memory.md](memory.md). See the [tool catalog](../README.md#capabilities). Other clients with local stdio MCP support can use the same command, arguments and environment. Client-specific configuration differs.

## Command-line usage

From the SEA source folder (or any directory after installation):

```sh
export SEA_MEDIA_ROOTS=/absolute/path/to/media
python -m sea.cli /absolute/path/to/media/demo.avi --duration 6
```

PowerShell:

```powershell
$env:SEA_MEDIA_ROOTS = 'C:\Users\YOU\SEA-Media'
python -m sea.cli 'C:\Users\YOU\SEA-Media\demo.avi' --duration 6
```

Generate a synthetic fixture using `python examples/make_demo.py /absolute/path/to/media/demo.avi`. It refuses to overwrite an existing output. The source generator writes a finite AVI directly in Python.

## Install the official Agent Skill

With Node.js installed, run `npx skills add PCTestAdmin/SEA --skill sea-perception` and review the selected agent and installation destination. This installs guidance only; the separate MCP setup above remains necessary. See [skill source](../skills/sea-perception/SKILL.md). For OCR, install Tesseract and the desired language packs; see [image tools](images.md).

## Optional Vision AI

See [Vision AI](vision-ai.md) for the separate dependency and explicit checkpoint setup. Normal SEA tools require no model weights.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| MCP server fails to start | Correct Python interpreter, SEA package installed, SDK import succeeds |
| FFmpeg not found | Both ffmpeg and ffprobe on client PATH; restart the client |
| Media outside configured directories | Use an absolute path inside an existing configured root |
| No audio or frame results | Check stream metadata and choose a segment within the media duration |
| Decode times out | Reduce the analysis window and use supported, trusted media |

## Measurement and privacy limits

SEA accepts local files only and uses fixed decoder arguments. Resolved paths outside configured roots are rejected. This is not an OS sandbox; use trusted files, avoid shared writable folders, concurrent path replacement and network mounts, and keep FFmpeg patched. No SEA uploads or remote API calls are required for analysis; the MCP client may transmit tool results to its AI provider.

Only the first audio/video stream is analyzed. Audio is downmixed to mono at 16 kHz. Video measurements are sampled at 4 fps in 160×90 grayscale. Timestamps are approximate, not exact source PTS; events between samples may be missed. Low-level bins use an RMS threshold below −40 dBFS. Visual-change flags use a normalized mean pixel difference of at least 0.12. These heuristics do not establish object motion, causation, physical loudness or diagnosis. Null dBFS with observed audio means zero amplitude. File limit: 2 GiB. Segment limits: 60 seconds for sense_media, 120 seconds for sense_video and 30 seconds for acoustic/investigation tools. Decoder timeout: 45 seconds per operation.

## Development

```sh
python -m pip install .
python -m unittest discover -s tests -v
```

The integration test uses a real MCP SDK stdio client; it skips if the SDK is absent locally. CI explicitly imports the SDK before running the tests. The current prototype includes a setup helper but no .mcpb extension or public PyPI package.
