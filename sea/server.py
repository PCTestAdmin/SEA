"""MCP stdio entry point; SEA never opens a listening socket."""
from mcp.server.fastmcp import FastMCP, Image
from .engine import resolve_media, probe, analyze, frame

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

def main():
    mcp.run(transport='stdio')

if __name__=='__main__':
    main()
