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
