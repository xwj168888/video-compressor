"""Flask web app for the video compressor.

File-backed job storage so multiple gunicorn workers share state correctly.
Flow:
  1. Client uploads file via POST /api/compress  (XHR progress on client)
  2. Server saves, probes, compresses (SSE progress via /api/progress/<id>)
  3. Client downloads result via /api/download/<id>
"""

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, send_from_directory, Response
from werkzeug.utils import secure_filename
from compressor import Compressor, PROFILES

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024 * 1024  # 5 GB

DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent)))
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
JOBS_DIR = DATA_DIR / "jobs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _read_job(job_id: str) -> dict:
    p = _job_path(job_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _write_job(job_id: str, data: dict):
    _job_path(job_id).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _remove_job(job_id: str):
    _job_path(job_id).unlink(missing_ok=True)


@app.route("/")
def index():
    return send_from_directory(Path(__file__).parent / "templates", "index.html")


@app.route("/api/profiles")
def api_profiles():
    return jsonify({
        k: {"name": v["name"], "description": v["description"]}
        for k, v in PROFILES.items()
    })


@app.route("/api/compress", methods=["POST"])
def api_compress():
    """Upload, probe, and compress — all in one request."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "请上传文件"}), 400

    profile = request.form.get("profile", "ai")
    target_size = request.form.get("target_size")
    if target_size:
        target_size = float(target_size)

    job_id = uuid.uuid4().hex
    filename = secure_filename(f.filename or "video.mp4")
    stem = Path(filename).stem
    input_path = UPLOAD_DIR / f"{job_id}_{filename}"
    output_name = f"{stem}_compressed.mp4"
    output_path = OUTPUT_DIR / f"{job_id}_{output_name}"

    _write_job(job_id, {"progress": 0, "status": "uploading", "output": None, "error": None})

    # Save uploaded file
    f.save(str(input_path))
    _write_job(job_id, {"progress": 0, "status": "probing", "output": None, "error": None})

    try:
        from compressor.utils import get_video_info
        info = get_video_info(str(input_path))

        def on_progress(pct, info_dict):
            _write_job(job_id, {
                "progress": pct,
                "status": info_dict.get("status", f"压缩中 {pct}%"),
                "output": None,
                "error": None,
            })

        compressor = Compressor(progress_callback=on_progress)
        result = compressor.compress(
            input_path=str(input_path),
            output_path=str(output_path),
            profile=profile,
            target_size_mb=target_size,
        )

        in_size = input_path.stat().st_size
        out_size = Path(result).stat().st_size

        _write_job(job_id, {
            "progress": 100,
            "status": "done",
            "output": {
                "filename": output_name,
                "download_url": f"/api/download/{job_id}",
                "input_size_mb": round(in_size / 1024 / 1024, 2),
                "output_size_mb": round(out_size / 1024 / 1024, 2),
                "ratio": round((1 - out_size / in_size) * 100),
                "input_info": {
                    "width": info.get("width"),
                    "height": info.get("height"),
                    "fps": info.get("fps"),
                    "duration": info.get("duration"),
                    "codec": info.get("codec"),
                },
            },
            "error": None,
        })
    except Exception as e:
        _write_job(job_id, {"progress": 0, "status": "error", "output": None, "error": str(e)})
    finally:
        input_path.unlink(missing_ok=True)

    return jsonify({"job_id": job_id})


@app.route("/api/progress/<job_id>")
def api_progress(job_id):
    """SSE endpoint for real-time compression progress (reads from file)."""
    def stream():
        import time
        last_pct = -1
        while True:
            job = _read_job(job_id)
            pct = job.get("progress", 0)
            status = job.get("status", "")
            err = job.get("error")
            out = job.get("output")

            if pct != last_pct or err or out:
                data = {"progress": pct, "status": status}
                if err:
                    data["error"] = err
                if out:
                    data["output"] = out
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                last_pct = pct

            if pct >= 100 or err:
                break
            time.sleep(0.3)

    return Response(stream(), mimetype="text/event-stream")


@app.route("/api/download/<job_id>")
def api_download(job_id):
    """Download the compressed video."""
    job = _read_job(job_id)
    if not job.get("output"):
        return "Not found", 404
    filename = job["output"]["filename"]
    result_path = OUTPUT_DIR / f"{job_id}_{filename}"
    if not result_path.exists():
        return "File not found", 404
    return send_from_directory(
        OUTPUT_DIR,
        f"{job_id}_{filename}",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/cleanup/<job_id>", methods=["DELETE"])
def api_cleanup(job_id):
    """Remove output file and job record after download."""
    job = _read_job(job_id)
    if job and job.get("output"):
        filename = job["output"]["filename"]
        (OUTPUT_DIR / f"{job_id}_{filename}").unlink(missing_ok=True)
    _remove_job(job_id)
    return jsonify({"ok": True})
