#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path


def _sdk_user_message(content: str) -> str:
    return json.dumps(
        {
            "type": "user",
            "content": content,
            "uuid": str(uuid.uuid4()),
            "session_id": "",
            "message": {"role": "user", "content": content},
            "parent_tool_use_id": None,
            "priority": "now",
        },
        ensure_ascii=False,
    )


def _assistant_text(payload: dict) -> str:
    message = payload.get("message") or {}
    content = message.get("content") or payload.get("content") or []
    if isinstance(content, str):
        return content
    parts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif item.get("type") == "thinking" and isinstance(item.get("thinking"), str):
                    parts.append(item["thinking"])
    return "\n".join(parts)


def _should_inject(payload: dict, started_at: float, saw_progress: bool) -> bool:
    if payload.get("type") == "assistant":
        text = _assistant_text(payload)
        if any(
            marker in text
            for marker in (
                "Let me make the changes",
                "Now I have the exact file contents",
                "I need to",
                "I'll",
            )
        ):
            return True
        content = (payload.get("message") or {}).get("content") or payload.get("content") or []
        if isinstance(content, list) and any(
            isinstance(item, dict) and item.get("type") == "tool_use" for item in content
        ):
            return True
    if saw_progress and time.monotonic() - started_at > 45:
        return True
    return False


def main() -> int:
    instruction_path = Path(sys.argv[1])
    injection_path = Path(sys.argv[2])
    log_path = Path(sys.argv[3])

    instruction = instruction_path.read_text()
    injection = injection_path.read_text()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "claude",
        "--verbose",
        "--input-format=stream-json",
        "--output-format=stream-json",
        "--permission-mode=bypassPermissions",
        "--print",
        "--replay-user-messages",
    ]

    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local/bin'}:{env.get('PATH', '')}"

    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        assert proc.stdin is not None
        assert proc.stdout is not None

        proc.stdin.write(_sdk_user_message(instruction) + "\n")
        proc.stdin.flush()

        injected = False
        saw_progress = False
        started_at = time.monotonic()

        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            log.flush()

            payload: dict | None = None
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = None

            if payload is not None and payload.get("type") in {"assistant", "system"}:
                saw_progress = True

            if not injected and payload is not None and _should_inject(
                payload, started_at, saw_progress
            ):
                marker = {
                    "type": "system",
                    "subtype": "harness_trajecdebug_interactive_icl_injected",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                marker_line = json.dumps(marker, ensure_ascii=False)
                sys.stdout.write(marker_line + "\n")
                sys.stdout.flush()
                log.write(marker_line + "\n")
                log.flush()

                proc.stdin.write(_sdk_user_message(injection) + "\n")
                proc.stdin.flush()
                injected = True

            if (
                payload is not None
                and payload.get("type") == "result"
                and payload.get("terminal_reason") == "completed"
            ):
                proc.stdin.close()

        return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
