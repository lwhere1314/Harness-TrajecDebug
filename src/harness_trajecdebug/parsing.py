"""Trace parsing utilities."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from harness_trajecdebug.models import Evidence, StateEvent


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_space(text: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def step_blob(step: dict[str, Any]) -> str:
    """Flatten common trace fields into a searchable text blob."""

    parts: list[str] = []
    for key in ("text", "reasoning", "observation"):
        value = step.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    for call in step.get("toolCalls") or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name")
        args = call.get("args")
        if name:
            parts.append(str(name))
        if isinstance(args, str):
            parts.append(args)
        elif isinstance(args, dict):
            parts.append(json.dumps(args, ensure_ascii=False))
    return "\n".join(parts)


def step_index(step: dict[str, Any], fallback: int) -> int:
    value = step.get("index")
    if isinstance(value, int):
        return value
    return fallback


def is_diagnostic_noise(text: str) -> bool:
    """Skip harness/skill boilerplate that can mention unrelated task names."""

    return bool(
        re.search(r"name:\s*terminal-bench-harbor-runner|# Terminal Bench Harbor Runner", text, re.I)
    )


def verifier_accuracy_failure(verifier_log: str) -> re.Match[str] | None:
    return re.search(r"Accuracy\s+([0-9.]+)\s+is not at least\s+([0-9.]+)", verifier_log)


def verifier_has_test_failure(verifier_log: str) -> bool:
    return bool(
        verifier_accuracy_failure(verifier_log)
        or re.search(r"AssertionError|=+\s+FAILURES\s+=+|\bFAILED\s+\S+|\"status\"\s*:\s*\"failed\"", verifier_log, re.I)
    )


def verifier_has_test_pass(verifier_log: str) -> bool:
    return bool(re.search(r"\b\d+\s+passed\b|\[100%\]|\bPASSED\b", verifier_log, re.I))


def detect_task_family(trace: dict[str, Any], trace_path: Path, run_id: str | None) -> str:
    identity = f"{run_id or ''}\n{trace_path.name}\n{trace_path.parent.name}".lower()
    if "cancel-async" in identity or "cancel async" in identity:
        return "cancel-async-tasks"
    if "train-fasttext" in identity or "fasttext" in identity:
        return "train-fasttext"

    prompt_blobs: list[str] = []
    for step in trace.get("steps", [])[:8]:
        blob = step_blob(step)
        if is_diagnostic_noise(blob):
            continue
        if step.get("role") == "user":
            prompt_blobs.append(blob)
    if not prompt_blobs:
        prompt_blobs = [
            step_blob(step)
            for step in trace.get("steps", [])[:5]
            if not is_diagnostic_noise(step_blob(step))
        ]
    haystack = "\n".join(prompt_blobs).lower()
    if "cancel-async" in haystack or "cancel async" in haystack:
        return "cancel-async-tasks"
    if "train-fasttext" in haystack or "fasttext" in haystack:
        return "train-fasttext"
    return "generic-terminal-agent"


def extract_reference(trace: dict[str, Any], task_family: str) -> dict[str, Any]:
    first_steps = "\n".join(step_blob(s) for s in trace.get("steps", [])[:3])
    reference: dict[str, Any] = {
        "source": "trace task prompt and verifier text",
        "artifact_path": None,
        "size_limit_bytes": None,
        "metric": None,
        "metric_threshold": None,
    }

    artifact = re.search(r"(/[A-Za-z0-9_./-]*model\.bin)", first_steps)
    if artifact:
        reference["artifact_path"] = artifact.group(1)
    elif task_family == "train-fasttext":
        reference["artifact_path"] = "/app/model.bin"

    size = re.search(r"(?:less than|<)\s*(\d+(?:\.\d+)?)\s*(MiB|MB|M)", first_steps, re.I)
    if size:
        reference["size_limit_bytes"] = int(float(size.group(1)) * 1024 * 1024)
    elif task_family == "train-fasttext":
        reference["size_limit_bytes"] = 150 * 1024 * 1024

    metric = re.search(r"(?:P@1|accuracy)[^\d]{0,20}(?:>=|at least|get at least)?\s*(0\.\d+)", first_steps, re.I)
    if metric:
        reference["metric"] = "P@1"
        reference["metric_threshold"] = float(metric.group(1))
    elif task_family == "train-fasttext":
        reference["metric"] = "P@1"
        reference["metric_threshold"] = 0.62

    if task_family == "cancel-async-tasks":
        reference.update(
            {
                "expected_behavior": "run_tasks should cancel active async tasks and await cleanup under failures or outer cancellation",
                "verifier": "pytest task tests",
            }
        )

    return reference


def dedupe_events(events: list[StateEvent]) -> list[StateEvent]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[StateEvent] = []
    for event in events:
        key = (
            str(event.step_index),
            event.kind,
            json.dumps(event.value, ensure_ascii=False, sort_keys=True),
            event.evidence,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(event)
    return result


def extract_state_events(trace: dict[str, Any]) -> list[StateEvent]:
    events: list[StateEvent] = []
    for fallback, step in enumerate(trace.get("steps", [])):
        idx = step_index(step, fallback)
        blob = step_blob(step)
        if is_diagnostic_noise(blob):
            continue

        for match in re.finditer(r"\bP@1\s+([0-9.]+)", blob):
            events.append(
                StateEvent(idx, "public_or_verifier_p_at_1", float(match.group(1)), normalize_space(match.group(0)))
            )

        for match in re.finditer(r"(\d{6,})\s+[A-Za-z]{3}\s+\d+\s+[\d:]+\s+(/[^\s]+model[^\s]*)", blob):
            events.append(
                StateEvent(
                    idx,
                    "artifact_size_bytes",
                    {"path": match.group(2), "bytes": int(match.group(1))},
                    normalize_space(match.group(0)),
                )
            )

        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*M\s+(/[^\s]+model[^\s]*)", blob):
            events.append(
                StateEvent(
                    idx,
                    "artifact_size_mib",
                    {"path": match.group(2), "mib": float(match.group(1))},
                    normalize_space(match.group(0)),
                )
            )

        for match in re.finditer(r"-dim\s+(\d+)", blob):
            events.append(StateEvent(idx, "fasttext_dim", int(match.group(1)), normalize_space(match.group(0))))

        for match in re.finditer(r"-wordNgrams\s+(\d+)", blob):
            events.append(StateEvent(idx, "fasttext_word_ngrams", int(match.group(1)), normalize_space(match.group(0))))

        if re.search(r"\bquantiz(?:e|ed|ation)|\.ftz\b", blob, re.I):
            events.append(StateEvent(idx, "quantization_or_ftz", True, normalize_space(blob)))

        if re.search(r"\bkilled\b|exit code 137|EXIT:\s*137|timeout", blob, re.I):
            events.append(StateEvent(idx, "budget_or_memory_failure", True, normalize_space(blob)))

    verifier = trace.get("verifierLog") or ""
    accuracy_failure = verifier_accuracy_failure(verifier)
    if accuracy_failure:
        events.append(
            StateEvent(
                None,
                "final_verifier_accuracy_failure",
                {"actual": float(accuracy_failure.group(1)), "threshold": float(accuracy_failure.group(2))},
                normalize_space(accuracy_failure.group(0)),
            )
        )

    if not accuracy_failure and re.search(
        r"cannot (?:be )?open|No such file|not found|does not exist|Could not parse", verifier, re.I
    ):
        events.append(StateEvent(None, "final_artifact_validation_failure", True, normalize_space(verifier[-600:])))

    if verifier_has_test_failure(verifier) and verifier_has_test_pass(verifier):
        events.append(StateEvent(None, "verifier_summary", "mixed_pass_fail", normalize_space(verifier[-600:])))

    return dedupe_events(events)


def extract_decision_evidence(trace: dict[str, Any]) -> list[Evidence]:
    evidence: list[Evidence] = []
    patterns = [
        (
            "final_promotion",
            r"saved to [`']?/app/model\.bin|cp\s+[^\n]*model[^\n]*/app/model\.bin|Final model size|requirement met|Done\.",
        ),
        ("validation_commitment", r"accuracy.*(?:met|above|enough)|P@1.*(?:>=|above|met)|public.*(?:enough|good)"),
        ("compression_commitment", r"quantiz(?:e|ed|ation)|compress(?:ed|ion)?|\.ftz"),
        ("route_choice", r"try|continue|use|switch|lower|increase|dim|wordNgrams"),
    ]
    for fallback, step in enumerate(trace.get("steps", [])):
        if step.get("role") == "user":
            continue
        idx = step_index(step, fallback)
        blob = step_blob(step)
        if is_diagnostic_noise(blob):
            continue
        for kind, pattern in patterns:
            if re.search(pattern, blob, re.I):
                evidence.append(Evidence("trace", idx, kind, normalize_space(blob)))
                break
    return evidence
