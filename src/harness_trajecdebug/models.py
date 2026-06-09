"""Data models for trajectory diagnosis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Evidence:
    """A compact quote or observation supporting a diagnosis."""

    source: str
    step_index: int | None
    kind: str
    text: str


@dataclass
class StateEvent:
    """A structured state observation extracted from a trace."""

    step_index: int | None
    kind: str
    value: Any
    evidence: str


@dataclass
class FailurePattern:
    """An evidence-grounded failure category."""

    name: str
    confidence: float
    rationale: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Diagnosis:
    """Full diagnostic output for one terminal-agent run."""

    run_id: str | None
    task_family: str
    outcome: str
    final_failure: str | None
    reference: dict[str, Any]
    state_summary: dict[str, Any]
    state_events: list[StateEvent]
    decision_evidence: list[Evidence]
    failure_patterns: list[FailurePattern]
    critical_step: dict[str, Any] | None
    diagnosis: str
    repair_hint: str | None
