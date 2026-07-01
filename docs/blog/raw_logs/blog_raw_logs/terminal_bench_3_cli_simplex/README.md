# Terminal-Bench 3 `cli-2ph-simplex` Raw Logs

This directory contains the raw evidence bundle for
[`terminal-bench-3-cli-simplex-mcts-critical-step.md`](../../../../case-studies/terminal-bench-3-cli-simplex-mcts-critical-step.md).
It preserves the two Harbor / Claude Code trajectories cited by the case study
and the small search artifacts used to derive the reward-1 Debug-Action path.

Credential/session files such as `.credentials.json`, Claude session backups,
and local key material are intentionally excluded. The selected text logs are
mechanically redacted for credential-like assignments while preserving the
original trajectory, transcript, verifier, and result structure.

## Evidence Map

| Case-study condition | Trial directory | Reward | Verifier footprint | Key evidence |
| --- | --- | ---: | --- | --- |
| `No TD` | [`cli-2ph-simplex__PiTA9w7`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629/cli-2ph-simplex__PiTA9w7) | `0.0` | `50 failed, 53 passed` | [`trajectory.json`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629/cli-2ph-simplex__PiTA9w7/agent/trajectory.json), [`claude-code.txt`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629/cli-2ph-simplex__PiTA9w7/agent/claude-code.txt), [`test-stdout.txt`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629/cli-2ph-simplex__PiTA9w7/verifier/test-stdout.txt), [`ctrf.json`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629/cli-2ph-simplex__PiTA9w7/verifier/ctrf.json) |
| `First interactive TD card` | [`cli-2ph-simplex__2QHadn3`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3) | `0.0` | `63 failed, 40 passed` | [`trajectory.json`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/trajectory.json), [`claude-code.txt`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/claude-code.txt), [`test-stdout.txt`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/verifier/test-stdout.txt), [`ctrf.json`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/verifier/ctrf.json) |

## TD Injection Evidence

The first interactive TD run preserves the injected context material:

- [`agent/interactive_icl_hint.txt`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/interactive_icl_hint.txt)
- [`agent/interactive_icl_instruction.txt`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/interactive_icl_instruction.txt)
- [`agent/trajectory.json`](harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/trajectory.json)

The case study cites this run because injection succeeded but the card was too
broad to identify the first actionable Phase 1 state transition.

## Search Evidence

The MCTS-like repair search was Codex-in-the-loop rather than a single Harbor
agent trajectory. The bundle keeps the compact artifacts needed to audit the
claimed reward-1 path:

- [`teacher_cards/tb3-cli-2ph-simplex-debug-action.md`](teacher_cards/tb3-cli-2ph-simplex-debug-action.md)
- [`teacher_cards/tb3-cli-2ph-simplex-debug-action-v2.md`](teacher_cards/tb3-cli-2ph-simplex-debug-action-v2.md)
- [`teacher_cards/tb3-cli-2ph-simplex-mcts-reward1-path.md`](teacher_cards/tb3-cli-2ph-simplex-mcts-reward1-path.md)
- [`search_probes/ge.txt`](search_probes/ge.txt)
- [`search_probes/fuzz2.txt`](search_probes/fuzz2.txt)

## Checksums

[`checksums.sha256`](checksums.sha256) records SHA-256 checksums for every file
in this evidence bundle after redaction.
