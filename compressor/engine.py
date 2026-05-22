"""Core video compression engine using FFmpeg.

Auto-detects the best available hardware encoder:
  - Intel QSV (h264_qsv / hevc_qsv)       — Intel Arc / integrated GPU
  - NVIDIA NVENC (h264_nvenc / hevc_nvenc) — NVIDIA GPU
  - AMD AMF (h264_amf / hevc_amf)          — AMD GPU
  - Apple VideoToolbox                     — macOS
  - Software x264 / x265                   — fallback
"""

import os
import shutil
import subprocess
import sys
import platform
from pathlib import Path
from .utils import get_video_info
from .profiles import get_profile


def _find_ffmpeg() -> str:
    """Locate the ffmpeg binary, adding known Windows install paths."""
    if platform.system() == "Windows":
        known = [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build-shared\bin"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
            r"C:\ffmpeg\bin",
        ]
        for d in known:
            if os.path.isdir(d) and d not in os.environ.get("PATH", ""):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    return "ffmpeg"


def _check_hw_available(enc: str) -> bool:
    """Check that the hardware backing *enc* is actually available, not just compiled in."""
    if enc.endswith("_vaapi") or enc.endswith("_qsv"):
        # VA-API / QSV both need the DRI render node
        return os.path.exists("/dev/dri/renderD128")
    if enc.endswith("_nvenc"):
        return shutil.which("nvidia-smi") is not None
    if enc.endswith("_amf"):
        return platform.system() == "Windows"
    return True


def _detect_hw_encoder(codec: str) -> str | None:
    """Return the best hardware encoder for *codec* ('h264' or 'hevc'), or None."""
    system = platform.system()

    if system == "Darwin":
        return "h264_videotoolbox" if codec == "h264" else "hevc_videotoolbox"

    if system == "Windows":
        preferred = [
            f"{codec}_qsv",
            f"{codec}_nvenc",
            f"{codec}_amf",
        ]
    else:
        preferred = [
            f"{codec}_vaapi",
            f"{codec}_nvenc",
            f"{codec}_qsv",
        ]

    _find_ffmpeg()
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        )
        for enc in preferred:
            if enc in result.stdout and _check_hw_available(enc):
                return enc
    except Exception:
        pass
    return None


class Compressor:
    """Compress video files using FFmpeg with hardware acceleration."""

    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback or (lambda p, info: None)

    def compress(
        self,
        input_path: str,
        output_path: str | None = None,
        profile: str = "ai",
        target_size_mb: float | None = None,
        custom: dict | None = None,
    ) -> str:
        input_path = str(input_path)
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        _find_ffmpeg()
        info = get_video_info(input_path)
        cfg = get_profile(profile).copy()

        if custom:
            cfg.update(custom)

        if output_path is None:
            p = Path(input_path)
            output_path = str(p.parent / f"{p.stem}_compressed.mp4")

        cmd = self._build_command(input_path, output_path, info, cfg, target_size_mb)

        self.progress_callback(0, {"status": "开始压缩...", "input_info": info})
        self._run_ffmpeg(cmd, info["duration"])
        self.progress_callback(100, {"status": "压缩完成"})

        return output_path

    def _build_command(self, input_path, output_path, info, cfg, target_size_mb):
        cmd = ["ffmpeg", "-y", "-i", input_path]

        # --- Video filter chain ---
        filters = []
        scale_filter = self._scale_filter(info, cfg)
        if scale_filter:
            filters.append(scale_filter)
        fps_filter = self._fps_filter(info, cfg)
        if fps_filter:
            filters.append(fps_filter)
        if filters:
            cmd.extend(["-vf", ",".join(filters)])

        # --- Video encoder ---
        codec = cfg["codec"]  # "hevc" or "h264"
        hw_enc = _detect_hw_encoder(codec)

        if hw_enc:
            self._apply_hw_encoder(cmd, hw_enc, cfg, codec)
        else:
            self._apply_sw_encoder(cmd, codec, cfg)

        # Target size: calculate required video bitrate
        if target_size_mb and info["duration"] > 0:
            audio_kbps = int(cfg["audio_bitrate"].replace("k", ""))
            target_kbps = (target_size_mb * 8192) / info["duration"]
            video_kbps = max(100, target_kbps - audio_kbps)
            cmd.extend(["-b:v", f"{int(video_kbps)}k"])
            cmd.extend(["-maxrate", f"{int(video_kbps * 1.5)}k"])
            cmd.extend(["-bufsize", f"{int(video_kbps * 2)}k"])

        # --- Audio ---
        if info["has_audio"]:
            cmd.extend(["-c:a", "aac", "-b:a", cfg["audio_bitrate"]])
        else:
            cmd.extend(["-an"])

        # --- Muxer ---
        cmd.extend(["-movflags", "+faststart"])
        cmd.append(output_path)

        return cmd

    def _apply_hw_encoder(self, cmd, hw_enc, cfg, codec):
        """Configure a hardware encoder."""
        cmd.extend(["-c:v", hw_enc])

        if "videotoolbox" in hw_enc:
            cmd.extend(["-q:v", str(cfg["quality"])])
            cmd.extend(["-allow_sw", "1"])
        elif "qsv" in hw_enc:
            # Intel QSV: use global_quality (1-51, lower = better)
            q = max(1, min(51, int((100 - cfg["quality"]) * 0.51)))
            cmd.extend(["-global_quality:v", str(q)])
            cmd.extend(["-preset", cfg.get("preset", "medium")])
        elif "nvenc" in hw_enc:
            q = max(1, min(51, int((100 - cfg["quality"]) * 0.51)))
            cmd.extend(["-qp:v", str(q)])
            cmd.extend(["-preset", "p4"])
        elif "amf" in hw_enc:
            cmd.extend(["-quality", "quality"])
            cmd.extend(["-q:v", str(cfg["crf"])])
        elif "vaapi" in hw_enc:
            cmd.extend(["-qp:v", str(cfg["crf"])])

        # Tag for QuickTime compatibility
        if codec == "hevc":
            cmd.extend(["-tag:v", "hvc1"])
        else:
            cmd.extend(["-tag:v", "avc1"])

    def _apply_sw_encoder(self, cmd, codec, cfg):
        """Configure a software encoder."""
        if codec == "hevc":
            cmd.extend(["-c:v", "libx265"])
            cmd.extend(["-crf", str(cfg["crf"])])
            cmd.extend(["-preset", cfg["preset"]])
            cmd.extend(["-tag:v", "hvc1"])
        else:
            cmd.extend(["-c:v", "libx264"])
            cmd.extend(["-crf", str(cfg["crf"])])
            cmd.extend(["-preset", cfg["preset"]])

        # 2-pass for software encoding — commented out for speed
        # cmd.extend(["-x265-params", "log-level=error"])

    def _scale_filter(self, info, cfg):
        max_w = cfg.get("max_width", 0)
        max_h = cfg.get("max_height", 0)
        if max_w <= 0 or max_h <= 0:
            return None
        w, h = info["width"], info["height"]
        if w <= max_w and h <= max_h:
            return None
        return (
            f"scale='min({max_w},iw)':'min({max_h},ih)'"
            ":force_original_aspect_ratio=decrease:force_divisible_by=2"
        )

    def _fps_filter(self, info, cfg):
        max_fps = cfg.get("max_fps", 0)
        if max_fps <= 0 or info["fps"] <= max_fps:
            return None
        return f"fps={max_fps}"

    def _run_ffmpeg(self, cmd: list, duration: float):
        """Run ffmpeg and stream progress via stderr parsing."""
        creationflags = 0
        if platform.system() == "Windows":
            creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        proc = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )

        for line in proc.stderr:
            line = line.strip()
            if "time=" in line:
                for part in line.split():
                    if part.startswith("time="):
                        time_str = part.split("=", 1)[1]
                        break
                else:
                    continue
                if duration > 0:
                    secs = self._time_to_secs(time_str)
                    pct = min(99, int(secs / duration * 100))
                    self.progress_callback(pct, {
                        "status": f"压缩中 {pct}%",
                        "time": time_str,
                    })

        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"ffmpeg exited with code {ret}")

    @staticmethod
    def _time_to_secs(t: str) -> float:
        parts = t.replace(",", ".").split(":")
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        return 0
