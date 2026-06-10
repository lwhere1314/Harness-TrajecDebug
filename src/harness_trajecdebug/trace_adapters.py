"""Adapters from common harness trace formats into the local trace schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_trace_for_diagnosis(path: Path) -> dict[str, Any]:
    """Load a trace file and normalize it for the rule-based diagnosis engine."""

    if path.suffix.lower() == ".jsonl":
        return normalize_codex_jsonl(path)

    obj = json.loads(path.read_text(encoding="utf-8"))
    return normalize_trace_object(obj, source_path=path)


def normalize_trace_object(obj: Any, source_path: Path | None = None) -> dict[str, Any]:
    """Return a diagnosis-ready trace dictionary.

    The native schema is already a dictionary with ``steps`` where each step uses
    ``text``, ``reasoning``, ``observation``, and ``toolCalls``. Claude Code's
    ATIF traces use ``message``, ``reasoning_content``, ``observation`` and
    ``tool_calls``; those are normalized here.
    """

    if not isinstance(obj, dict):
        return {
            "steps": [
                {
                    "index": 0,
                    "role": "assistant",
                    "text": _coerce_text(obj),
                }
            ],
            "verifierLog": "",
        }

    steps = obj.get("steps")
    if not isinstance(steps, list):
        return dict(obj)

    if _looks_like_native_trace(obj):
        trace = dict(obj)
        trace.setdefault("verifierLog", obj.get("verifier_log") or "")
        return trace

    if _looks_like_atif_trace(obj):
        return normalize_atif_trace(obj, source_path=source_path)

    normalized = dict(obj)
    normalized["steps"] = [_normalize_step(step, idx) for idx, step in enumerate(steps) if isinstance(step, dict)]
    normalized.setdefault("verifierLog", obj.get("verifier_log") or "")
    return normalized


def normalize_atif_trace(obj: dict[str, Any], source_path: Path | None = None) -> dict[str, Any]:
    """Normalize a Claude Code / ATIF-style trajectory."""

    trace: dict[str, Any] = {
        "sourceSchema": obj.get("schema_version") or obj.get("schemaVersion") or "ATIF-like",
        "sessionId": obj.get("session_id"),
        "agent": obj.get("agent"),
        "steps": [],
        "verifierLog": obj.get("verifierLog") or obj.get("verifier_log") or "",
    }
    if source_path is not None:
        trace["sourcePath"] = str(source_path)

    for fallback, raw_step in enumerate(obj.get("steps", [])):
        if not isinstance(raw_step, dict):
            continue
        trace["steps"].append(_normalize_step(raw_step, fallback))

    return trace


def normalize_codex_jsonl(path: Path) -> dict[str, Any]:
    """Normalize Codex CLI/Desktop JSONL event streams.

    The Codex streams observed in local Harbor runs mix JSON event records with
    plain-text log lines. Non-JSON lines are skipped.
    """

    trace: dict[str, Any] = {
        "sourceSchema": "codex-jsonl",
        "sourcePath": str(path),
        "steps": [],
        "verifierLog": "",
    }

    pending_calls: dict[str, dict[str, Any]] = {}
    index = 0
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        for step in _codex_event_steps(event, index, pending_calls):
            trace["steps"].append(step)
            index += 1

        thread_id = event.get("thread_id") or (event.get("payload") or {}).get("thread_id")
        if thread_id and "threadId" not in trace:
            trace["threadId"] = thread_id

    return trace


def _looks_like_native_trace(obj: dict[str, Any]) -> bool:
    steps = obj.get("steps") or []
    for step in steps:
        if not isinstance(step, dict):
            continue
        if any(key in step for key in ("text", "reasoning", "toolCalls")):
            return True
    return False


def _looks_like_atif_trace(obj: dict[str, Any]) -> bool:
    schema = str(obj.get("schema_version") or obj.get("schemaVersion") or "")
    if schema.startswith("ATIF"):
        return True
    for step in obj.get("steps") or []:
        if isinstance(step, dict) and any(key in step for key in ("message", "tool_calls", "reasoning_content")):
            return True
    return False


def _normalize_step(raw_step: dict[str, Any], fallback: int) -> dict[str, Any]:
    role = _normalize_role(raw_step.get("role") or raw_step.get("source"))
    index = raw_step.get("index")
    if index is None:
        index = raw_step.get("step_id")
    if index is None:
        index = fallback

    step: dict[str, Any] = {
        "index": index,
        "role": role,
    }

    text = _coerce_text(raw_step.get("text") or raw_step.get("message") or raw_step.get("content"))
    if text:
        step["text"] = text

    reasoning = _clean_reasoning(raw_step.get("reasoning") or raw_step.get("reasoning_content"))
    if reasoning:
        step["reasoning"] = reasoning

    observation = _observation_to_text(raw_step.get("observation"))
    if observation:
        step["observation"] = observation

    tool_calls = _normalize_tool_calls(raw_step.get("toolCalls") or raw_step.get("tool_calls"))
    if tool_calls:
        step["toolCalls"] = tool_calls

    if raw_step.get("timestamp"):
        step["timestamp"] = raw_step.get("timestamp")
    if raw_step.get("model_name"):
        step["modelName"] = raw_step.get("model_name")
    extra = raw_step.get("extra")
    if isinstance(extra, dict) and extra.get("cwd"):
        step["cwd"] = extra.get("cwd")

    if not any(key in step for key in ("text", "reasoning", "observation", "toolCalls")):
        step["text"] = _coerce_text(raw_step)

    return step


def _normalize_role(value: Any) -> str:
    role = str(value or "assistant").lower()
    if role in {"agent", "assistant", "model"}:
        return "assistant"
    if role in {"user", "system", "tool"}:
        return role
    return role or "assistant"


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return "" if value == "null" else value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _clean_reasoning(value: Any) -> str:
    text = _coerce_text(value).strip()
    if text.lower() in {"", "null", "none"}:
        return ""
    return text


def _observation_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        results = value.get("results")
        if isinstance(results, list):
            parts = []
            for result in results:
                if isinstance(result, dict):
                    content = result.get("content")
                    if content is not None:
                        parts.append(_coerce_text(content))
            if parts:
                return "\n".join(parts)
        metadata = value.get("metadata") or value.get("tool_result_metadata")
        if isinstance(metadata, dict):
            tool_result = metadata.get("tool_use_result")
            if isinstance(tool_result, dict):
                stdout = _coerce_text(tool_result.get("stdout"))
                stderr = _coerce_text(tool_result.get("stderr"))
                return "\n".join(part for part in (stdout, stderr) if part)
    return _coerce_text(value)


def _normalize_tool_calls(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for call in value:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("function_name") or call.get("tool_name")
        args = call.get("args")
        if args is None:
            args = call.get("arguments")
        normalized: dict[str, Any] = {}
        if name:
            normalized["name"] = name
        if args is not None:
            normalized["args"] = args
        if call.get("tool_call_id"):
            normalized["id"] = call.get("tool_call_id")
        if normalized:
            result.append(normalized)
    return result


def _codex_event_steps(
    event: dict[str, Any],
    index: int,
    pending_calls: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    event_type = event.get("type")
    payload = event.get("payload")
    steps: list[dict[str, Any]] = []

    if event_type == "item.completed":
        item = event.get("item") or {}
        item_type = item.get("type")
        if item_type == "agent_message":
            text = _coerce_text(item.get("text"))
            if text:
                steps.append({"index": index, "role": "assistant", "text": text})
        elif item_type == "command_execution":
            steps.append(_command_execution_step(item, index))
        return steps

    if isinstance(payload, dict):
        payload_type = payload.get("type")
        if payload_type == "message":
            text = _message_payload_text(payload)
            if text:
                steps.append({"index": index, "role": payload.get("role") or "assistant", "text": text})
        elif payload_type == "function_call":
            call_id = str(payload.get("call_id") or payload.get("id") or index)
            call = {
                "name": payload.get("name"),
                "args": _decode_json_maybe(payload.get("arguments")),
            }
            pending_calls[call_id] = call
            steps.append({"index": index, "role": "assistant", "toolCalls": [call]})
        elif payload_type == "function_call_output":
            call_id = str(payload.get("call_id") or payload.get("id") or index)
            call = pending_calls.pop(call_id, {})
            step: dict[str, Any] = {
                "index": index,
                "role": "assistant",
                "observation": _coerce_text(payload.get("output")),
            }
            if call:
                step["toolCalls"] = [call]
            steps.append(step)
        elif payload_type == "event_msg" and payload.get("message"):
            steps.append({"index": index, "role": "assistant", "text": _coerce_text(payload.get("message"))})

    return steps


def _command_execution_step(item: dict[str, Any], index: int) -> dict[str, Any]:
    command = _coerce_text(item.get("command"))
    output = _coerce_text(item.get("aggregated_output") or item.get("output"))
    status = item.get("status")
    exit_code = item.get("exit_code")
    observation = output
    if exit_code is not None or status:
        observation = "\n".join(part for part in (output, f"status={status} exit_code={exit_code}") if part)
    return {
        "index": index,
        "role": "assistant",
        "toolCalls": [{"name": "command_execution", "args": {"command": command}}],
        "observation": observation,
    }


def _message_payload_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(_coerce_text(item.get("text") or item.get("output_text")))
            else:
                parts.append(_coerce_text(item))
        return "\n".join(part for part in parts if part)
    return _coerce_text(content)


def _decode_json_maybe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
