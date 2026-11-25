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

## Connect to an MCP client

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

Restart the MCP client and verify that SEA exposes three tools: inspect_media, sense_media, view_frame. Other clients with local stdio MCP support can use the same command, arguments and environment. Client-specific configuration differs.

## Command-line usage

From the SEA source folder (or any directory after installation):

```sh
export SEA_MEDIA_ROOTS=/absolute/path/to/media
python -m sea.cli /absolute/path/to/media/demo.mp4 --duration 6
```

PowerShell:

```powershell
$env:SEA_MEDIA_ROOTS = 'C:\Users\YOU\SEA-Media'
python -m sea.cli 'C:\Users\YOU\SEA-Media\demo.mp4' --duration 6
```

Generate a synthetic fixture using `python examples/make_demo.py /absolute/path/to/media/demo.mp4`. It refuses to overwrite an existing output. The source generator uses FFmpeg.

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

Only the first audio/video stream is analyzed. Audio is downmixed to mono at 16 kHz. Video measurements are sampled at 4 fps in 160×90 grayscale. Timestamps are approximate, not exact source PTS; events between samples may be missed. Low-level bins use an RMS threshold below −40 dBFS. Visual-change flags use a normalized mean pixel difference of at least 0.12. These heuristics do not establish object motion, causation, physical loudness or diagnosis. Null dBFS with observed audio means zero amplitude. File limit: 2 GiB. Segment limit: 60 seconds. Decoder timeout: 45 seconds per operation.

## Development

```sh
python -m pip install .
python -m unittest discover -s tests -v
```

The integration test uses a real MCP SDK stdio client; it skips if the SDK is absent locally. CI explicitly imports the SDK before running the tests. The current prototype does not include a one-click extension or published package.
