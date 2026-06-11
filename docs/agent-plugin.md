# Agent Plugin Compatibility

Harness-TrajecDebug can be exposed to Claude Code, Codex, and Kimi Code through
the same local skill package:

```text
plugins/harness-trajdebug-agent/
```

The package contains:

- `.codex-plugin/plugin.json` for Codex plugin installs,
- `kimi.plugin.json` for Kimi Code plugin installs,
- `skills/trajectorydebug/SKILL.md` for trace diagnosis and Debug-Action cards,
- `skills/harness-runtime-icl/SKILL.md` for runtime ICL canaries,
- `scripts/htd-agent` as a thin wrapper around `harness-trajdebug` and the
  existing runtime ICL scripts.

## Product boundary

The intended product is a harness-agnostic TrajectoryDebug plugin layer:

1. The harness still owns task setup, container orchestration, verifier
   execution, rewards, and raw run storage.
2. Harness-TrajecDebug owns trace normalization, failure diagnosis,
   critical-step extraction, Debug-Action card selection, runtime ICL injection,
   and no-TD versus with-TD evidence comparison.
3. Claude Code, Codex, and Kimi Code should see the same one-click interface:
   run or import an experiment, analyze the resulting trace, synthesize a
   compact repair card, rerun with a bounded injection mode, and export the
   evidence bundle.

The current V1 surface is skill plus CLI wrapper. The next stable product
surface should be an MCP server exposing structured tools such as
`run_experiment`, `diagnose_trace`, `select_debug_card`, `rerun_with_context`,
`compare_runs`, and `export_evidence_bundle`.

## One-command project install

From the repo root:

```bash
python3 scripts/install_agent_plugin.py
```

This installs project-local skill shims into:

```text
.claude/skills/
.agents/skills/
.kimi-code/skills/
```

Then restart the target CLI in this repository.

## Claude Code

Claude Code can use project skills from:

```text
.claude/skills/trajectorydebug/SKILL.md
.claude/skills/harness-runtime-icl/SKILL.md
```

Use:

```text
/trajectorydebug diagnose this Harbor run
/harness-runtime-icl run a no-TD versus with-TD canary
```

Meta-Harness uses the same broad pattern: it ships `.claude/skills/...` and a
`claude_wrapper.py` that explicitly loads those skills. The released
Meta-Harness examples assume Claude Code as the proposer; other proposer agents
require adapting their wrapper.

## Codex

Codex can use the project-local `.agents/skills/` shims after restart. The same
capability is also packaged as a Codex plugin source at:

```text
plugins/harness-trajdebug-agent/.codex-plugin/plugin.json
```

The plugin is skill-only for now. It does not start an MCP server during
session startup.

## Kimi Code

Kimi Code scans project-local `.agents/skills/` and `.kimi-code/skills/`.
It can also install the plugin directly:

```text
/plugins install /Users/hugo/Projects/Harness-TrajecDebug/plugins/harness-trajdebug-agent
```

After installation, restart or run `/reload`.

## Smoke check

Run:

```bash
plugins/harness-trajdebug-agent/scripts/htd-agent doctor
```

The command checks whether `harness-trajdebug`, `claude`, `codex`, and `kimi`
are on `PATH`, and whether the local skill directories are present.

## Runtime ICL environment

`sdk_live` is stricter than normal trace diagnosis because it runs a Python
Claude Agent SDK bridge inside the Harbor task container. Before using it as
evidence, check these separately:

- Host CLI layer: `claude`, `codex`, and optionally `kimi` are on `PATH`.
- Endpoint layer: `SEED_CODING_PLAN_BASE_URL` and
  `SEED_CODING_PLAN_API_KEY` are present, and `kimi-k2.6` returns a small
  Anthropic-compatible Messages response.
- Target container layer: `python3 -m pip --version` works before Claude Code
  starts, or the task image is prebuilt with Python/pip.
- SDK dependency layer: use `claude-agent-sdk==0.1.43`, `mcp>=1.27.2`,
  `httpx==0.28.1`, and `httpcore==1.0.9`.

If the task image lacks Python/pip or PyPI access is flaky, prebuild a runtime
image or wheelhouse first. Treat missing Python, old `mcp` imports such as
`ToolAnnotations`, pip resolver backtracking, and package download timeouts as
environment failures, not Harness-TrajecDebug algorithm failures.

For live evidence, keep:

```text
agent/sdk-live-events.jsonl
agent/sdk-install.log
agent/command-*/stdout.txt
runner.log
verifier/test-stdout.txt
result.json
```

## Current boundary

This is the V1 compatibility layer:

- shared skills work across Claude Code, Codex, and Kimi Code,
- CLI commands remain the execution boundary,
- no automatic MCP server is declared yet.

The next layer should add `harness-trajdebug-mcp` with tools such as
`diagnose_trace`, `diagnose_harbor_run`, `select_debug_card`, `compare_runs`,
and `export_atif_bundle`.
