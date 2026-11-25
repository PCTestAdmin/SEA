"""MCP stdio entry point; SEA never opens a listening socket."""
from mcp.server.fastmcp import FastMCP, Image
from .engine import resolve_media, probe, analyze, frame
from .acoustics import analyze_audio, compare_audio, spectrogram
from .vision import analyze_video, investigate
from .spatial import sense_spatial, crop_region
from .signals import analyze_signals

mcp = FastMCP('SEA', instructions='Analyze only user-authorized local media. Measurements are observations, not diagnoses. Do not invent semantic meaning, causes or events from numerical evidence. Media results may be visible to the AI provider.')

@mcp.tool()
def inspect_media(path: str) -> dict:
    """Read metadata from a local audio/video file in SEA_MEDIA_ROOTS. No uploads by SEA."""
    return probe(resolve_media(path))

@mcp.tool()
def sense_media(path: str, start_s: float = 0, duration_s: float = 15) -> dict:
    """Measure audio levels, dominant frequency and frame differences on a shared timeline. Use 0.25–60 second windows; no transcription or semantic interpretation. Only permitted local files."""
    return analyze(resolve_media(path),start_s,duration_s)

@mcp.tool()
def view_frame(path: str, time_s: float) -> Image:
    """Return one sampled visual frame near the requested time. The image is sent to the MCP host/model; obtain user permission for sensitive media."""
    data=frame(resolve_media(path),time_s)
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('No frame found at requested time.')
    return Image(data=data,format='png')

@mcp.tool()
def sense_audio(path: str, start_s: float = 0, duration_s: float = 15) -> dict:
    """Measure spectral peaks, band power, 100 ms levels and fixed-threshold level events in an authorized local recording (0.25–30 s). No sound identification."""
    return analyze_audio(resolve_media(path), start_s, duration_s)

@mcp.tool()
def audio_spectrogram(path: str, start_s: float = 0, duration_s: float = 15, max_hz: int = 8000) -> Image:
    """Return a spectrogram PNG of an authorized local segment (0.25–30 s). Time left to right, frequency bottom 0 Hz to top floor(max_hz/15.625)*15.625 Hz. Dark navy -90 dBFS to pale yellow 0 dBFS, Hann amplitude estimates; up to 900 time columns. Use sense_audio for numeric evidence. Image is sent to the host/model."""
    return Image(data=spectrogram(resolve_media(path), start_s, duration_s, max_hz), format='png')

@mcp.tool()
def compare_recordings(path_a: str, path_b: str, start_a_s: float = 0, start_b_s: float = 0, duration_s: float = 15) -> dict:
    """Compare equally long authorized local audio segments (0.25–30 s). Differences are B minus A; no automatic alignment or quality judgment."""
    return compare_audio(resolve_media(path_a), resolve_media(path_b), start_a_s, start_b_s, duration_s)

@mcp.tool()
def sense_video(path: str, start_s: float = 0, duration_s: float = 30) -> dict:
    """Measure sampled pixel changes, histogram shifts, change regions and low-change intervals in authorized local video (0.25–120 s). No object tracking or confirmed scene cuts."""
    return analyze_video(resolve_media(path),start_s,duration_s)

@mcp.tool()
def investigate_media(path: str, start_s: float = 0, duration_s: float = 15, tolerance_s: float = .5) -> dict:
    """Build an evidence-indexed audio/video investigation report (0.25–30 s). Correlate nearby level transitions and visual changes, then suggest frame timestamps. Proximity is not causation; interpret only with evidence."""
    return investigate(resolve_media(path),start_s,duration_s,tolerance_s)

@mcp.tool()
def inspect_spatial(path: str, time_s: float = 0, grid_size: int = 3) -> dict:
    """Measure image-space layout, regional colors and contrast in a local PNG/JPEG or video frame. Normalized image coordinates, no physical depth or object recognition."""
    return sense_spatial(resolve_media(path,allow_image=True),time_s,grid_size)

@mcp.tool()
def inspect_region(path: str, box: list[float], time_s: float = 0) -> Image:
    """Return a PNG crop of the downsampled visual sample. Box [left,top,right,bottom], normalized 0–1. Image goes to the MCP host/model."""
    return Image(data=crop_region(resolve_media(path,allow_image=True),time_s,box),format='png')

@mcp.tool()
def sense_signals(path: str, time_column: str, channels: list[str], change_thresholds: dict[str,float] | None = None) -> dict:
    """Analyze authorized numeric UTF-8 CSV sensor logs: explicit seconds column, 1–8 value columns, optional adjacent-change thresholds in channel units. Return statistics, event times and paired-row correlations. No live device access or calibration."""
    return analyze_signals(resolve_media(path,allow_csv=True),time_column,channels,change_thresholds)

def main():
    mcp.run(transport='stdio')

if __name__=='__main__':
    main()
