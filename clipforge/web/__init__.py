"""Flask application factory for ClipForge web UI."""

import tempfile
from pathlib import Path

from flask import Flask, jsonify


def create_app(work_dir: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.config["WORK_DIR"] = work_dir or Path(tempfile.mkdtemp(prefix="clipforge_"))
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024  # 10 GB

    from clipforge.web.routes import bp
    app.register_blueprint(bp)

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({"error": "File too large"}), 413

    return app
