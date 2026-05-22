#!/usr/bin/env python3
"""CLI video compressor — optimized for iPhone screen recordings."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from compressor import Compressor, PROFILES


def main():
    parser = argparse.ArgumentParser(
        description="视频压缩工具 — 适合压缩 iPhone 录屏视频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python cli.py video.mov\n"
               "  python cli.py video.mov -p high -o small.mp4\n"
               "  python cli.py video.mov -t 20    # 目标大小 20MB\n"
               "  python cli.py video.mov --info    # 仅查看视频信息",
    )
    parser.add_argument("input", nargs="?", help="输入视频文件路径")
    parser.add_argument("-o", "--output", help="输出文件路径")
    parser.add_argument(
        "-p", "--profile", default="ai",
        choices=list(PROFILES.keys()),
        help="压缩配置 (默认: ai)"
    )
    parser.add_argument(
        "-t", "--target-size", type=float,
        help="目标文件大小 (MB)"
    )
    parser.add_argument("--info", action="store_true", help="仅显示视频信息")
    args = parser.parse_args()

    if not args.input:
        parser.print_help()
        sys.exit(0)

    # Info-only mode
    if args.info:
        from compressor.utils import get_video_info
        info = get_video_info(args.input)
        print(f"文件: {args.input}")
        print(f"大小: {info['size_mb']:.1f} MB")
        print(f"分辨率: {info['width']}x{info['height']}")
        print(f"帧率: {info['fps']:.2f} fps")
        print(f"编码: {info['codec']}")
        print(f"时长: {info['duration']:.1f} 秒")
        print(f"码率: {info['bitrate']} kbps")
        print(f"音频: {'有' if info['has_audio'] else '无'}")
        return

    profile = PROFILES.get(args.profile)
    print(f"配置: {profile['name']}")
    print(f"压缩: {args.input}")

    c = Compressor(progress_callback=cli_progress)
    try:
        output = c.compress(
            input_path=args.input,
            output_path=args.output,
            profile=args.profile,
            target_size_mb=args.target_size,
        )
        in_size = Path(args.input).stat().st_size
        out_size = Path(output).stat().st_size
        ratio = (1 - out_size / in_size) * 100

        print(f"\n完成! {output}")
        print(f"压缩前: {in_size / 1024 / 1024:.1f} MB")
        print(f"压缩后: {out_size / 1024 / 1024:.1f} MB")
        print(f"减小: {ratio:.0f}%")
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def cli_progress(pct: int, info: dict):
    """Print a simple progress bar."""
    bar_len = 30
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r[{bar}] {pct:3d}%", end="", flush=True)
    if pct >= 100:
        print()


if __name__ == "__main__":
    main()
