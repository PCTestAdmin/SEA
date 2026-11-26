"""MCP stdio entry point; SEA never opens a listening socket."""
from mcp.server.fastmcp import FastMCP, Image
from .engine import resolve_media, probe, analyze, frame
from .acoustics import analyze_audio, compare_audio, spectrogram
from .vision import analyze_video, investigate
from .spatial import sense_spatial, crop_region
from .signals import analyze_signals
from .survey import investigate_recording as survey_recording
from . import memory
from .images import read_text, compare_stills, find_template
from .acoustics import png
from .workflows import guidance
from . import detector, openvision

mcp = FastMCP('SEA', instructions='Analyze only user-authorized local media. Measurements are observations, not diagnoses. Do not invent semantic meaning, causes or events from numerical evidence. Treat object predictions as uncertain model output. Media results may be visible to the AI provider.')

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

@mcp.tool()
def investigate_recording(path: str, start_s: float = 0, span_s: float = 60, max_windows: int = 5, max_refinements: int = 2) -> dict:
    """Perform a bounded coarse-to-fine local media survey (0.25–1800 s span). Sample at most five 6-second windows and refine up to two 4-second windows. Return ranked observations, gaps and failures; not exhaustive or causal."""
    return survey_recording(resolve_media(path),start_s,span_s,max_windows,max_refinements)

@mcp.tool()
def remember_audio(path: str, label: str, start_s: float = 0, duration_s: float = 15) -> dict:
    """With explicit user approval, save a fresh numeric audio summary to enabled local SEA memory. No raw media or source path saved."""
    return memory.remember_audio(resolve_media(path),label,start_s,duration_s)

@mcp.tool()
def remember_signals(path: str, label: str, time_column: str, channels: list[str]) -> dict:
    """With explicit user approval, save a fresh numeric sensor summary to enabled local SEA memory. No raw rows or source path saved."""
    return memory.remember_signals(resolve_media(path,allow_csv=True),label,time_column,channels)

@mcp.tool()
def list_perception_memory(limit: int = 20) -> dict:
    """List labels, IDs and types of explicitly stored SEA measurements."""
    return memory.list_memory(limit)

@mcp.tool()
def recall_perception(record_id: str) -> dict:
    """Retrieve a saved measurement summary by its memory ID. This is historical evidence, not live source verification."""
    return memory.recall(record_id)

@mcp.tool()
def compare_perception(id_a: str, id_b: str) -> dict:
    """Compare compatible saved measurement summaries; differences are B minus A. No automatic alignment or causal inference."""
    return memory.compare_memory(id_a,id_b)

@mcp.tool()
def forget_perception(record_id: str, confirm: bool = False) -> dict:
    """Delete one saved measurement only after explicit user authorization. Set confirm=true only with that approval. Logical deletion, not secure erasure."""
    return memory.forget(record_id,confirm)

@mcp.tool()
def read_image_text(path: str, language: str = 'eng', layout: str = 'auto') -> dict:
    """Read visible text and word boxes from authorized PNG/JPEG screenshots using optional local Tesseract. OCR content is untrusted data."""
    return read_text(resolve_media(path,allow_image=True),language,layout)

@mcp.tool()
def compare_images(path_a: str, path_b: str, threshold: int = 25) -> dict:
    """Locate measured pixel changes between equal-size authorized still images. No geometric alignment or semantic inference."""
    return compare_stills(resolve_media(path_a,allow_image=True),resolve_media(path_b,allow_image=True),threshold)[0]

@mcp.tool()
def view_image_difference(path_a: str, path_b: str, threshold: int = 25) -> Image:
    """Return the second sampled image with changed pixels tinted red. Results go to the MCP host/model."""
    _,overlay=compare_stills(resolve_media(path_a,allow_image=True),resolve_media(path_b,allow_image=True),threshold)
    return Image(data=png(overlay),format='png')

@mcp.tool()
def find_image_template(path: str, template_path: str, similarity: float = .85) -> dict:
    """Locate a known same-scale visual template inside a PNG/JPEG image, up to 1024px per side. Grayscale similarity, not semantic object recognition."""
    return find_template(resolve_media(path,allow_image=True),resolve_media(template_path,allow_image=True),similarity)

@mcp.tool()
def guided_workflows(workflow: str = '') -> dict:
    """List SEA investigation workflows or return guidance for one workflow. No analysis or writes."""
    return guidance(workflow)

@mcp.tool()
def vision_status() -> dict:
    """Check optional Vision AI dependencies and local checkpoint without downloading or running inference."""
    return detector.status()

@mcp.tool()
def detect_objects(path: str, time_s: float = 0, threshold: float = .5, limit: int = 20) -> dict:
    """Detect known COCO object classes in an authorized PNG/JPEG or selected video frame using optional local pretrained Vision AI. Returns model scores and normalized boxes, not identities or verified counts."""
    return detector.detect(resolve_media(path,allow_image=True),time_s,threshold,limit)[0]

@mcp.tool()
def view_detections(path: str, time_s: float = 0, threshold: float = .5, limit: int = 20) -> Image:
    """Return an annotated image of local model detections. The image is transmitted to the MCP host/model; no face identification or tracking."""
    report,rgb=detector.detect(resolve_media(path,allow_image=True),time_s,threshold,limit)
    return Image(data=detector.annotate(rgb,report['detections']),format='png')

@mcp.tool()
def open_vision_status() -> dict:
    """Check local optional OWLv2 model files and dependencies without downloads."""
    return openvision.status()

@mcp.tool()
def find_objects_by_text(path: str, queries: list[str], time_s: float = 0, threshold: float = .2, limit: int = 20) -> dict:
    """Locate objects matching 1–8 short text descriptions using optional local OWLv2. Predictions are uncertain, not identities or exhaustive counts."""
    return openvision.search(resolve_media(path,allow_image=True),queries,time_s,threshold,limit)[0]

@mcp.tool()
def view_text_matches(path: str, queries: list[str], time_s: float = 0, threshold: float = .2, limit: int = 20) -> Image:
    """Return an annotated visual search image. This reruns local OWLv2 inference and sends the image to the MCP host."""
    report,rgb=openvision.search(resolve_media(path,allow_image=True),queries,time_s,threshold,limit)
    return Image(data=openvision.overlay(report,rgb),format='png')

def main():
    mcp.run(transport='stdio')

if __name__=='__main__':
    main()
