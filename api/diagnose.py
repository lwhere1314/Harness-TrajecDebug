from __future__ import annotations

import json
import sys
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harness_trajecdebug.diagnose import diagnose_trace  # noqa: E402


EXAMPLES = {
    "train-fasttext": {
        "label": "train-fasttext near miss",
        "run_id": "train-fasttext-kimi-k26-minimal",
        "trace": ROOT / "examples" / "traces" / "train-fasttext-kimi-k26-minimal.json",
    },
    "cancel-async-tasks": {
        "label": "cancel-async-tasks passed",
        "run_id": "cancel-async-tasks-passed-minimal",
        "trace": ROOT / "examples" / "traces" / "cancel-async-tasks-passed-minimal.json",
    },
}


def run_example(name: str) -> dict:
    example = EXAMPLES[name]
    diagnosis = diagnose_trace(example["trace"], run_id=example["run_id"])
    payload = asdict(diagnosis)
    payload["example_label"] = example["label"]
    return payload


class handler(BaseHTTPRequestHandler):
    def _send_text(self, status: int, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=0, must-revalidate")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_text(404, "Not found", "text/plain; charset=utf-8")
            return
        self._send_text(200, path.read_text(encoding="utf-8"), content_type)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send_file(ROOT / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/styles.css":
            self._send_file(ROOT / "styles.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self._send_file(ROOT / "app.js", "application/javascript; charset=utf-8")
            return
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if parsed.path != "/api/diagnose":
            self._send_json(404, {"ok": False, "error": f"Unknown path: {parsed.path}"})
            return

        query = parse_qs(parsed.query)
        selected = query.get("example", ["all"])[0]
        try:
            if selected == "all":
                payload = {
                    "ok": True,
                    "examples": [run_example(name) for name in EXAMPLES],
                }
            elif selected in EXAMPLES:
                payload = {
                    "ok": True,
                    "example": run_example(selected),
                }
            else:
                payload = {
                    "ok": False,
                    "error": f"Unknown example: {selected}",
                    "available": sorted(EXAMPLES),
                }
                self._send_json(404, payload)
                return
            self._send_json(200, payload)
        except Exception as exc:  # pragma: no cover - last-resort API guard
            self._send_json(500, {"ok": False, "error": str(exc)})
