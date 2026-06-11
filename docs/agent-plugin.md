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

For long Harbor runs launched from Codex, use the detached launcher. Codex's
shell tool may clean up plain `nohup ... &` children after the tool call
returns, while the launcher starts the runner in a new session:

```bash
python3 scripts/launch_query_optimize_sdk_live_repro.py \
  runs/harbor_icl_repro_codex_launch \
  --context-variant fail_debug_action
```

The tested Codex path is:

```text
Codex skill -> detached launcher -> Harness wrapper -> Claude Code SDK sdk_live
-> kimi-k2.6 through the SEED Anthropic-compatible endpoint
```

Direct `codex exec -m kimi-k2.6` against the SEED endpoint is not treated as
the supported path unless an OpenAI Responses-compatible adapter is available.
In local smoke testing, nested `codex exec` did not complete even for a trivial
`echo CODEX_EXEC_OK` command, including with a temporary clean `CODEX_HOME`.
Do not present direct Codex CLI execution as verified until that local
CLI/provider path can pass the echo gate and then the compact recorded demo.

## Kimi Code

Kimi Code scans project-local `.agents/skills/` and `.kimi-code/skills/`.
It can also install the plugin directly:

```text
/plugins install /path/to/Harness-TrajecDebug/plugins/harness-trajdebug-agent
```

After installation, restart or run `/reload`.

For headless Kimi Code smoke tests with the SEED endpoint, prefer the repository
wrapper so secrets stay in the environment and project skills are loaded from
the Harness-TrajecDebug root:

```bash
scripts/run_kimicode_skill_smoke.sh
```

The wrapper maps `SEED_CODING_PLAN_BASE_URL` and
`SEED_CODING_PLAN_API_KEY` into Kimi Code's `KIMI_MODEL_BASE_URL` and
`KIMI_MODEL_API_KEY`, uses `KIMI_MODEL_PROVIDER_TYPE=anthropic`, and runs
`kimi-k2.6` through the local Kimi Code dev CLI.

For the recorded demo smoke, use a short explicit Bash instruction and let the
wrapper print the parsed summary. In current local testing this path completed
and produced the diagnosis plus closure artifacts, while longer "run and then
report every metric" prompts and slash-command-only Kimi prompts could start a
session and then stall before the first model response:

```bash
scripts/run_kimicode_skill_smoke.sh \
  'Use Bash to run: HTD_DEMO_PAUSE=0 plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --recorded --compact --out-dir /tmp/htd-kimi-recorded'
```

The wrapper runs Kimi through a PTY-friendly foreground monitor, disables Kimi
thinking by default for this smoke path, records stdout/stderr under
`runs/kimi_code_smoke/home/run-logs/`, and exits as soon as it sees recorded
demo completion or injection evidence.

For the full `query-optimize` runtime Debug-Action reproduction, use:

```bash
HTD_NO_FORCE_BUILD=1 HTD_KEEP_ENVIRONMENT=1 \
  scripts/run_query_optimize_sdk_live_repro.sh runs/harbor_icl_repro_seed fail_debug_action
```

From Codex, prefer the detached form shown above for the same reproduction.

For the recording demo, use the plugin wrapper so Claude Code, Codex, and Kimi
Code users all see the same entry point:

```bash
HTD_DEMO_PAUSE=1 HTD_DEMO_NO_FORCE_BUILD=1 HTD_DEMO_KEEP_ENVIRONMENT=1 \
  plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --live-fail-teacher
```

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
- Docker lifecycle layer: recording demos should pass `--no-force-build` and
  may pass `--keep-environment` so Harbor reuses warm images and preserves the
  task container for inspection.
- Query-optimize live demo layer: pass `--tag-local-hb-prebuilt` or set
  `HTD_DEMO_TAG_LOCAL_HB_PREBUILT=1` so Harbor's no-force path uses the local
  `hb__query-optimize:latest` image. The upstream
  `alexgshaw/query-optimize:20251031` image does not include Python/pip, which
  `sdk_live` needs before Claude Code starts.

For cold Harbor task images, run `sdk_live` with enough setup budget, for
example `--sdk-live-install-timeout 900 --agent-timeout 1800`. If the task image
needs to install Python/pip first, that time is separate from the SDK install
timeout but still counts against the overall agent timeout.

If the task image lacks Python/pip or PyPI access is flaky, prebuild a runtime
image or wheelhouse first. Treat missing Python, old `mcp` imports such as
`ToolAnnotations`, pip resolver backtracking, and package download timeouts as
environment failures, not Harness-TrajecDebug algorithm failures.

Harbor / Docker failures should be reported separately from model failures.
Common local signatures include Docker build exit `-9`, missing
`verifier/reward.txt`, `sdk_live Python/pip bootstrap failed`, and
`claude_init: false`.

## Verified entrypoints

| Entrypoint | Status |
| --- | --- |
| Claude Code headless prompt -> `htd-agent demo query-optimize --recorded --compact` | Verified locally: first reward `0`, closure passed, recorded with-TD reward `1`, `injection_count=1`. |
| Kimi Code smoke wrapper -> short explicit Bash prompt -> same compact recorded command | Verified locally: Kimi called `Bash`, the demo produced `critical_step`, `closure_passed`, recorded reward `1`, and `injection_count=1`. |
| Claude Code -> live `--live-fail-teacher --compact` | Verified to launch the real Harbor `sdk_live` path; current local failures were Docker/Python setup failures before valid injection evidence. |
| Nested `codex exec` prompt-mode run | Tested and not passing in this local environment: even `echo CODEX_EXEC_OK` exits before model/tool output. Keep Codex support to the app/thread skill path or detached launcher until CLI execution is fixed. |

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
