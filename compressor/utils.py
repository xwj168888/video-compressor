"""Utility functions for video compression."""

import json
import subprocess
from pathlib import Path


def get_video_info(path: str) -> dict:
    """Extract video metadata using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    video_stream = None
    audio_stream = None

    for stream in data.get("streams", []):
        if stream["codec_type"] == "video" and video_stream is None:
            video_stream = stream
        elif stream["codec_type"] == "audio" and audio_stream is None:
            audio_stream = stream

    if not video_stream:
        raise RuntimeError(f"No video stream found in {path}")

    return {
        "duration": float(fmt.get("duration", 0)),
        "size_bytes": int(fmt.get("size", 0)),
        "size_mb": round(int(fmt.get("size", 0)) / (1024 * 1024), 2),
        "width": video_stream.get("width", 0),
        "height": video_stream.get("height", 0),
        "fps": _parse_fps(video_stream),
        "codec": video_stream.get("codec_name", "unknown"),
        "bitrate": int(fmt.get("bit_rate", 0)) // 1000 if fmt.get("bit_rate") else 0,
        "has_audio": audio_stream is not None,
        "format_name": fmt.get("format_name", "unknown"),
    }


def _parse_fps(stream: dict) -> float:
    """Parse frame rate from stream info."""
    avg = stream.get("avg_frame_rate", "0/1")
    if "/" in avg:
        parts = avg.split("/")
        if parts[1] != "0":
            return round(float(parts[0]) / float(parts[1]), 2)
    r_frame_rate = stream.get("r_frame_rate", "0/1")
    if "/" in r_frame_rate:
        parts = r_frame_rate.split("/")
        if parts[1] != "0":
            return round(float(parts[0]) / float(parts[1]), 2)
    return 0


def parse_ffmpeg_progress(line: str) -> dict | None:
    """Parse a line of ffmpeg progress output."""
    if not line.startswith("out_time="):
        return None
    info = {}
    for part in line.strip().split():
        if "=" in part:
            k, v = part.split("=", 1)
            info[k] = v
    return info
