"""Top-level diagnosis orchestration."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from harness_trajecdebug.models import Diagnosis, StateEvent
from harness_trajecdebug.parsing import (
    as_float,
    as_int,
    detect_task_family,
    extract_decision_evidence,
    extract_reference,
    extract_state_events,
    verifier_has_test_failure,
    verifier_has_test_pass,
)
from harness_trajecdebug.patterns import choose_critical_step, classify_patterns, final_failure, make_diagnosis_text
from harness_trajecdebug.trace_adapters import load_trace_for_diagnosis


def read_metrics(path: Path | None, run_id: str | None) -> dict[str, str]:
    if not path or not run_id or not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("run_id") == run_id:
                return row
    return {}


def read_case_run(path: Path | None, run_id: str | None) -> dict[str, Any]:
    if not path or not run_id or not path.exists():
        return {}
    obj = load_trace_for_diagnosis(path)
    for run in obj.get("runs", []):
        if run.get("runId") == run_id:
            return run
    return {}


def summarize_state(
    events: list[StateEvent],
    metrics: dict[str, str] | None = None,
    case_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = metrics or {}
    case_run = case_run or {}
    p_values = [e.value for e in events if e.kind == "public_or_verifier_p_at_1" and isinstance(e.value, float)]
    size_values = [
        e.value["bytes"]
        for e in events
        if e.kind == "artifact_size_bytes" and isinstance(e.value, dict) and "bytes" in e.value
    ]
    final_accuracy = None
    final_threshold = None
    for event in events:
        if event.kind == "final_verifier_accuracy_failure" and isinstance(event.value, dict):
            final_accuracy = event.value.get("actual")
            final_threshold = event.value.get("threshold")

    final_model_bytes = as_int(metrics.get("final_model_bytes"))
    for event in events:
        if (
            event.kind == "artifact_size_bytes"
            and isinstance(event.value, dict)
            and event.value.get("path") == "/app/model.bin"
        ):
            final_model_bytes = event.value.get("bytes")

    features = case_run.get("features") or {}
    return {
        "passed": case_run.get("passed"),
        "reward": as_float(case_run.get("reward")) if case_run else as_float(metrics.get("reward")),
        "cluster": case_run.get("cluster") or metrics.get("cluster"),
        "best_public_p_at_1": max(p_values) if p_values else as_float(metrics.get("best_p_at_1")) or features.get("best_p_at_1"),
        "last_observed_p_at_1": p_values[-1] if p_values else None,
        "final_verifier_p_at_1": final_accuracy or as_float(metrics.get("final_verifier_p_at_1")),
        "metric_threshold": final_threshold,
        "max_observed_size_bytes": max(size_values) if size_values else as_int(metrics.get("max_size_bytes")) or features.get("max_size_bytes"),
        "final_model_bytes": final_model_bytes,
        "dims": sorted({e.value for e in events if e.kind == "fasttext_dim" and isinstance(e.value, int)})
        or features.get("dims"),
        "word_ngrams": sorted({e.value for e in events if e.kind == "fasttext_word_ngrams" and isinstance(e.value, int)})
        or features.get("wordNgrams"),
        "quantized_or_ftz_seen": any(e.kind == "quantization_or_ftz" for e in events) or bool(features.get("quantized")),
        "budget_or_memory_failures": sum(1 for e in events if e.kind == "budget_or_memory_failure"),
    }


def diagnose_trace(
    trace_path: Path,
    run_id: str | None = None,
    metrics_csv: Path | None = None,
    case_json: Path | None = None,
) -> Diagnosis:
    trace = load_trace_for_diagnosis(trace_path)
    verifier_log = trace.get("verifierLog") or ""
    task_family = detect_task_family(trace, trace_path, run_id)
    metrics = read_metrics(metrics_csv, run_id)
    case_run = read_case_run(case_json, run_id)
    if not case_run and isinstance(trace.get("harbor"), dict):
        case_run = trace["harbor"]
    reference = extract_reference(trace, task_family)
    events = extract_state_events(trace)
    decisions = extract_decision_evidence(trace)
    state = summarize_state(events, metrics, case_run)
    patterns = classify_patterns(reference, state, events, decisions, verifier_log)
    diagnosis_text, repair_hint = make_diagnosis_text(patterns)

    outcome = "passed" if any(p.name == "no critical failure detected" for p in patterns) else "failed"
    if case_run and case_run.get("passed") is True:
        outcome = "passed"
    elif case_run and case_run.get("passed") is False:
        outcome = "failed"
    elif verifier_has_test_pass(verifier_log) and not verifier_has_test_failure(verifier_log):
        outcome = "passed"

    failure = final_failure(events, verifier_log)
    if failure is None and case_run:
        reward = state.get("reward")
        if case_run.get("passed") is False or (isinstance(reward, float) and reward < 1.0):
            failure = f"Harbor reward={reward}" if reward is not None else "Harbor trial did not pass"

    return Diagnosis(
        run_id=run_id,
        task_family=task_family,
        outcome=outcome,
        final_failure=failure,
        reference=reference,
        state_summary=state,
        state_events=events,
        decision_evidence=decisions[:20],
        failure_patterns=patterns,
        critical_step=choose_critical_step(patterns),
        diagnosis=diagnosis_text,
        repair_hint=repair_hint,
    )
