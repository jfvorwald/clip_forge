"""Web UI routes for ClipForge."""

import json
import queue
import subprocess
import threading
import uuid
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)

from clipforge.engine import process
from clipforge.manifest import CaptionConfig, Manifest, SilenceCutConfig

bp = Blueprint("web", __name__, template_folder="templates", static_folder="static")

# In-memory job store: job_id -> job dict
_jobs: dict[str, dict] = {}


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    job_id = uuid.uuid4().hex[:12]
    job_dir = Path(current_app.config["WORK_DIR"]) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(f.filename).suffix or ".mp4"
    input_path = job_dir / f"input{ext}"
    f.save(input_path)

    _jobs[job_id] = {
        "dir": job_dir,
        "input_path": input_path,
        "filename": f.filename,
        "status": "uploaded",
    }

    return jsonify({"job_id": job_id, "filename": f.filename})


@bp.route("/api/jobs/<job_id>/process", methods=["POST"])
def start_process(job_id: str):
    if job_id not in _jobs:
        return jsonify({"error": "Job not found"}), 404

    job = _jobs[job_id]
    if job["status"] not in ("uploaded", "done", "error"):
        return jsonify({"error": f"Job is already {job['status']}"}), 409

    config = request.get_json() or {}
    input_path = job["input_path"]
    output_path = job["dir"] / f"output{input_path.suffix}"

    sc = config.get("silence_cut", {})
    cc = config.get("captions", {})

    manifest = Manifest(
        input=input_path,
        output=output_path,
        silence_cut=SilenceCutConfig(
            enabled=sc.get("enabled", False),
            threshold_db=float(sc.get("threshold_db", -30.0)),
            min_duration=float(sc.get("min_duration", 0.5)),
            padding=float(sc.get("padding", 0.05)),
        ),
        captions=CaptionConfig(
            enabled=cc.get("enabled", False),
            model=cc.get("model", "base"),
            output_format=cc.get("output_format", "srt"),
        ),
    )

    progress_queue: queue.Queue = queue.Queue()
    job["progress_queue"] = progress_queue
    job["status"] = "processing"
    job["error"] = None

    def run():
        try:
            def on_progress(stage: str, frac: float):
                progress_queue.put({"stage": stage, "progress": round(frac, 3)})

            result = process(manifest, on_progress=on_progress)
            job["result"] = {
                "output_path": str(result.output_path),
                "duration_original": result.duration_original,
                "duration_final": result.duration_final,
                "segments_removed": result.segments_removed,
            }
            job["status"] = "done"
        except subprocess.CalledProcessError as e:
            job["status"] = "error"
            stderr = e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode(errors="replace")
            job["error"] = f"ffmpeg failed: {stderr[-500:]}" if stderr else str(e)
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
        finally:
            progress_queue.put(None)  # sentinel

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})


@bp.route("/api/jobs/<job_id>/progress")
def progress_stream(job_id: str):
    if job_id not in _jobs:
        return jsonify({"error": "Job not found"}), 404

    job = _jobs[job_id]
    q = job.get("progress_queue")

    if q is None:
        return jsonify({"error": "No processing in progress"}), 409

    def generate():
        while True:
            try:
                msg = q.get(timeout=120)
            except queue.Empty:
                yield "data: {\"error\": \"timeout\"}\n\n"
                break
            if msg is None:
                if job["status"] == "error":
                    data = json.dumps({"error": job["error"]})
                else:
                    data = json.dumps({
                        "stage": "complete",
                        "progress": 1.0,
                        "result": job.get("result"),
                    })
                yield f"data: {data}\n\n"
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@bp.route("/api/jobs/<job_id>/result")
def download_result(job_id: str):
    if job_id not in _jobs:
        return jsonify({"error": "Job not found"}), 404

    job = _jobs[job_id]
    if job["status"] != "done":
        return jsonify({"error": "Job not complete"}), 409

    output_path = Path(job["result"]["output_path"])
    return send_file(output_path, as_attachment=False)


@bp.route("/api/jobs/<job_id>/status")
def job_status(job_id: str):
    if job_id not in _jobs:
        return jsonify({"error": "Job not found"}), 404

    job = _jobs[job_id]
    resp = {"status": job["status"], "filename": job.get("filename")}
    if job["status"] == "done":
        resp["result"] = job.get("result")
    if job["status"] == "error":
        resp["error"] = job.get("error")
    return jsonify(resp)
