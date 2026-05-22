#!/usr/bin/env python3
"""Video Compressor launcher — CLI or Web UI."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Ensure FFmpeg is discoverable on Windows
if sys.platform == "win32":
    from compressor.engine import _find_ffmpeg
    _find_ffmpeg()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        from web.app import app
        host = os.environ.get("HOST", "127.0.0.1")
        port = int(os.environ.get("PORT", "5050"))
        print()
        print("  视频压缩工具 — Web 界面")
        print(f"  打开浏览器访问: http://{host}:{port}")
        print()
        app.run(host=host, port=port, debug=False, threaded=True)
    else:
        from cli import main
        main()
