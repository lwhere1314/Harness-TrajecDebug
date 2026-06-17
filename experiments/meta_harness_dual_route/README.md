# Meta-Harness Dual Route Canary

This experiment separates two routes that should not be conflated.

Route A is the upstream-shaped Terminal-Bench route: Claude Code plus
`kimi-k2.6` is the proposer, and the evaluated candidate is a Python
`AgentHarness` subclassing Terminus2.

Route B is a Claude Code adaptation: Claude Code plus `kimi-k2.6` is both the
proposer family and the evaluated inner agent, but the search object remains a
general Claude Code wrapper. This is not a faithful upstream reproduction and
should be corrected before being presented as Meta-Harness.

Both routes forbid task-specific hints in candidate code, comments, prompts, or
wrapper logic. Historical failed trajectories may be inspected by a proposer,
but concrete task names, verifier test names, and failure diagnoses must not be
copied into the evaluated agent prompt or harness source.

The current canary runner is:

```bash
scripts/run_meta_harness_dual_route_canary.sh --route both --attempts 1
```

Use `--endpoint-profile seed-agent-plan` for the Seed Agent Plan Anthropic route.
Host model calls currently require `http://127.0.0.1:1082` as a proxy on this
machine.

Current status is tracked in `status_20260617.md`. In short:

- Route A is implemented with `Terminus2`, matching the upstream Terminal-Bench
  Meta-Harness shape. It did not improve `cancel-async-tasks`, but the
  follow-up `query-optimize` canary reproduces a positive Meta-Harness effect:
  pure Terminus2 + `kimi-k2.6` fails the runtime gate, while Route A passes.
- Route B is implemented as a Claude Code wrapper. It is useful as a diagnostic
  Claude Code adaptation attempt, but the `query-optimize` canary shows this
  adaptation is not correct: baseline Claude Code + `kimi-k2.6` passes, while
  the Route B wrapper fails the runtime gate.
- The matched Route B infra control uses the same Claude Code version
  (`2.1.157`), model, task image, endpoint, proxy, and Harbor environment, but
  omits the generic review prompt.
- Local task-copy infra patches are documented in the status file; the upstream
  task source was not modified.

The follow-up `query-optimize` ARM64 canary is documented in
`query_optimize_arm64_20260617.md`. It compares the matched Claude Code
baseline, Route B, pure Terminus2, and Route A on the same native ARM64 task
copy, including reward, token usage, latency, raw-log locations, and trajectory
diffs.
