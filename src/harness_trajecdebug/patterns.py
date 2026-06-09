"""Failure pattern classification and critical-step selection."""

from __future__ import annotations

import re

from harness_trajecdebug.models import Evidence, FailurePattern, StateEvent
from harness_trajecdebug.parsing import normalize_space, verifier_has_test_failure, verifier_has_test_pass


def first_evidence(events: list[StateEvent], kind: str) -> Evidence | None:
    for event in events:
        if event.kind == kind:
            return Evidence("state", event.step_index, kind, event.evidence)
    return None


def last_evidence(events: list[StateEvent], kind: str) -> Evidence | None:
    for event in reversed(events):
        if event.kind == kind:
            return Evidence("state", event.step_index, kind, event.evidence)
    return None


def last_decision(decisions: list[Evidence], kind: str) -> Evidence | None:
    matches = [item for item in decisions if item.kind == kind]
    return matches[-1] if matches else None


def classify_patterns(
    reference: dict[str, object],
    state: dict[str, object],
    events: list[StateEvent],
    decisions: list[Evidence],
    verifier_log: str,
) -> list[FailurePattern]:
    """Classify evidence-grounded process failures.

    The current MVP is intentionally rule-based. Rules should stay conservative:
    do not emit a failure pattern unless it has a final verifier footprint or
    another terminal signal.
    """

    if verifier_has_test_pass(verifier_log) and not verifier_has_test_failure(verifier_log):
        return [
            FailurePattern(
                name="no critical failure detected",
                confidence=0.95,
                rationale="Verifier passed; run can be used as positive evidence for closure behavior.",
                evidence=[],
            )
        ]

    patterns: list[FailurePattern] = []
    threshold = state.get("metric_threshold") or reference.get("metric_threshold")
    final_p = state.get("final_verifier_p_at_1")
    best_public = state.get("best_public_p_at_1")
    last_public = state.get("last_observed_p_at_1")

    if isinstance(final_p, float) and isinstance(threshold, float) and final_p < threshold:
        evidence: list[Evidence] = []
        verifier_evidence = first_evidence(events, "final_verifier_accuracy_failure")
        if verifier_evidence:
            evidence.append(verifier_evidence)
        last_metric = last_evidence(events, "public_or_verifier_p_at_1")
        if last_metric:
            evidence.append(last_metric)
        final_promotion = last_decision(decisions, "final_promotion")
        if final_promotion:
            evidence.append(final_promotion)

        if isinstance(best_public, float) and best_public >= threshold and (best_public - threshold) <= 0.01:
            patterns.append(
                FailurePattern(
                    name="thin-margin promotion",
                    confidence=0.88,
                    rationale=(
                        f"Best observed public P@1={best_public:.3f} barely cleared threshold {threshold:.3f}, "
                        f"but final verifier P@1={final_p:.3f} failed."
                    ),
                    evidence=evidence,
                )
            )
        elif isinstance(best_public, float) and best_public >= threshold and (best_public - final_p) >= 0.03:
            patterns.append(
                FailurePattern(
                    name="validation mismatch",
                    confidence=0.82,
                    rationale=(
                        f"Public validation P@1={best_public:.3f} was much higher than final verifier P@1={final_p:.3f}."
                    ),
                    evidence=evidence,
                )
            )
        else:
            patterns.append(
                FailurePattern(
                    name="accuracy objective gap",
                    confidence=0.70,
                    rationale=f"Final verifier P@1={final_p:.3f} did not meet threshold {threshold:.3f}.",
                    evidence=evidence,
                )
            )

    size_limit = reference.get("size_limit_bytes")
    max_size = state.get("max_observed_size_bytes")
    dims = state.get("dims") or []
    ngrams = state.get("word_ngrams") or []
    if (
        isinstance(size_limit, int)
        and isinstance(max_size, int)
        and max_size > size_limit
        and state.get("quantized_or_ftz_seen")
    ):
        compact_evidence: list[Evidence] = []
        size_ev = first_evidence(events, "artifact_size_bytes")
        quant_ev = first_evidence(events, "quantization_or_ftz")
        if size_ev:
            compact_evidence.append(size_ev)
        if quant_ev:
            compact_evidence.append(quant_ev)
        if 5 not in dims or 2 not in ngrams or (
            isinstance(last_public, float) and isinstance(threshold, float) and last_public - threshold <= 0.005
        ):
            patterns.append(
                FailurePattern(
                    name="compact-frontier search gap",
                    confidence=0.76,
                    rationale=(
                        "Trace shows size-aware compression, but the final candidate remained close to the accuracy "
                        "threshold; diagnosis is a weak joint search over compact size-accuracy candidates."
                    ),
                    evidence=compact_evidence,
                )
            )

    if any(e.kind == "final_artifact_validation_failure" for e in events):
        ev = first_evidence(events, "final_artifact_validation_failure")
        patterns.append(
            FailurePattern(
                name="final artifact validation",
                confidence=0.90,
                rationale="Final artifact was missing, unloadable, malformed, or failed verifier parsing.",
                evidence=[ev] if ev else [],
            )
        )

    api_error_count = len(
        re.findall(r"TypeError|SyntaxError|invalid argument|unknown option|failed building wheel|command not found", verifier_log, re.I)
    )
    if api_error_count >= 2:
        patterns.append(
            FailurePattern(
                name="tool/API loop",
                confidence=0.68,
                rationale=f"Verifier/trace text contains repeated tool or API error markers ({api_error_count}).",
                evidence=[],
            )
        )

    budget_failures = state.get("budget_or_memory_failures") or 0
    if isinstance(budget_failures, int) and budget_failures >= 2:
        evs = [
            Evidence("state", e.step_index, e.kind, e.evidence)
            for e in events
            if e.kind == "budget_or_memory_failure"
        ][:3]
        patterns.append(
            FailurePattern(
                name="budget debt loop",
                confidence=0.72,
                rationale=f"Trace contains {budget_failures} timeout / killed / exit-137 events.",
                evidence=evs,
            )
        )

    if not patterns and verifier_has_test_pass(verifier_log):
        patterns.append(
            FailurePattern(
                name="no critical failure detected",
                confidence=0.95,
                rationale="Verifier passed; run can be used as positive evidence for closure behavior.",
                evidence=[],
            )
        )

    return patterns


def choose_critical_step(patterns: list[FailurePattern]) -> dict[str, object] | None:
    failure_patterns = [p for p in patterns if p.name != "no critical failure detected"]
    if not failure_patterns:
        return None
    priority = {
        "validation mismatch": 0,
        "thin-margin promotion": 0,
        "compact-frontier search gap": 1,
        "accuracy objective gap": 2,
        "tool/API loop": 2,
        "budget debt loop": 3,
        "final artifact validation": 4,
    }
    ordered = sorted(failure_patterns, key=lambda p: (priority.get(p.name, 9), -p.confidence, p.name))
    top = ordered[0]
    indexed = [ev for ev in top.evidence if ev.step_index is not None]
    earliest = min(indexed, key=lambda ev: ev.step_index) if indexed else None
    return {
        "pattern": top.name,
        "step_index": earliest.step_index if earliest else None,
        "evidence": earliest.text if earliest else (top.evidence[0].text if top.evidence else None),
        "confidence": top.confidence,
    }


def final_failure(events: list[StateEvent], verifier_log: str) -> str | None:
    for event in events:
        if event.kind == "final_verifier_accuracy_failure" and isinstance(event.value, dict):
            return f"final verifier P@1={event.value['actual']} < threshold {event.value['threshold']}"
        if event.kind == "final_artifact_validation_failure":
            return "final artifact failed verifier validation"
    if verifier_has_test_failure(verifier_log):
        return normalize_space(verifier_log[-300:])
    return None


def make_diagnosis_text(patterns: list[FailurePattern]) -> tuple[str, str | None]:
    names = [p.name for p in patterns]
    if "no critical failure detected" in names:
        return (
            "No critical failure detected; verifier passed and the trace can serve as positive closure behavior.",
            None,
        )
    if "thin-margin promotion" in names and "compact-frontier search gap" in names:
        return (
            "Agent recognized the size gate, but promoted a compact candidate with too little accuracy margin; "
            "the likely issue is weak joint search over compact size-accuracy candidates.",
            "Continue compact low-dim / ngram sweeps and require a stronger validation margin before final promotion.",
        )
    if "validation mismatch" in names:
        return (
            "Agent over-trusted a local validation signal that did not match the final verifier.",
            "Replay the official verifier path earlier and gate final promotion on verifier-equivalent validation.",
        )
    if "final artifact validation" in names:
        return (
            "Agent did useful work but did not close the final artifact contract expected by the verifier.",
            "Add an artifact closure checklist: path, loadability, size, metric, and final verifier smoke test.",
        )
    if "budget debt loop" in names:
        return (
            "Agent spent repeated budget on routes already showing timeout or memory pressure.",
            "Introduce stop/checkpoint rules and prefer cheaper frontier probes before long training runs.",
        )
    return (
        "Trace-level diagnosis found candidate failure patterns that require manual review.",
        "Inspect the attached evidence snippets and add task-specific repair rules.",
    )
