"""Explicit MCP registration profiles; full remains backwards compatible."""
import os

VIDEO_TOOLS=frozenset({
    'inspect_media','compact_video_overview','view_frame','view_video_segment',
    'read_video_frames','view_video_frame_region','listen_video_segment',
    'sense_audio','analyze_target'
})
PROFILES=('full','video')


def profile_name(value=None):
    name=os.environ.get('SEA_MCP_PROFILE','full') if value is None else value
    if name not in PROFILES:
        raise ValueError('SEA_MCP_PROFILE must be full or video.')
    return name


def register_tool(server,profile,**kwargs):
    def decorate(fn):
        if profile=='full' or fn.__name__ in VIDEO_TOOLS:
            return server.tool(**kwargs)(fn)
        return fn
    return decorate


def register_prompt(server,profile,**kwargs):
    def decorate(fn):
        if profile=='full' or fn.__name__=='understand_video':
            return server.prompt(**kwargs)(fn)
        return fn
    return decorate
