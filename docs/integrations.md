# Harness and Harbor Integrations

Harness-TrajecDebug now has a lightweight integration layer for local terminal
agent harnesses and Harbor-compatible task/run directories.

## Harness Inventory

List locally discoverable harness backends:

```bash
PYTHONPATH=src python3 -m harness_trajecdebug.cli harnesses
```

The inventory currently models:

- `codex`: host CLI / host-runner traces, usually `agent/codex-exec.jsonl`.
- `claude-code`: Harbor native container agent traces, usually
  `agent/trajectory.json` in ATIF format.
- `kimi-code`: currently represented as Kimi K2.5/K2.6 routes through the
  Anthropic-compatible Claude Code runner; a standalone `kimi-code` executable
  will be picked up when it is installed on `PATH`.

The default SSD/Harbor locations are:

```text
/Users/hugo/Desktop/super-refactor/harbor
/Volumes/SSD/terminal-bench-harbor/harbor
```

Override the Harbor root with `HARBOR_ROOT` or pass `--ssd-root` to
`harnesses`.

## Harbor-Compatible Tasks

List tasks from a Harbor dataset root:

```bash
PYTHONPATH=src python3 -m harness_trajecdebug.cli harbor-tasks \
  --root /Volumes/SSD/terminal-bench-harbor/harbor/datasets/terminal-bench-2.1-proxy/tasks \
  --limit 5
```

The scanner is not hard-coded to Terminal-Bench. It treats any directory with
the Harbor task contract as a task:

```text
task.toml
instruction.md
environment/Dockerfile
solution/solve.sh
tests/test.sh
```

That keeps the same entry point open for later Harbor datasets such as
`swe-bench-pro`.

## Harbor Runs

List trials in a Harbor run:

```bash
PYTHONPATH=src python3 -m harness_trajecdebug.cli harbor-trials \
  --run /Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-train-fasttext-claude-code-kimi-k26
```

Normalize traces and diagnose them:

```bash
PYTHONPATH=src python3 -m harness_trajecdebug.cli harbor-import \
  --run /Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-train-fasttext-claude-code-kimi-k26 \
  --output-dir artifacts/normalized-harbor \
  --diagnose
```

The importer currently understands:

- Harbor native `agent/trajectory.json` ATIF traces from Claude Code.
- Codex CLI/Desktop JSONL streams from `agent/codex-exec.jsonl`.
- verifier logs from `verifier/test-stdout.txt`, `verifier/stdout.txt`, and the
  local hardened verifier smoke paths used by the Codex host runner.

You can also diagnose an ATIF JSON or Codex JSONL file directly:

```bash
PYTHONPATH=src python3 -m harness_trajecdebug.cli diagnose \
  --trace /path/to/agent/trajectory.json

PYTHONPATH=src python3 -m harness_trajecdebug.cli diagnose \
  --trace /path/to/agent/codex-exec.jsonl
```

Direct JSONL diagnosis has no verifier log unless the JSONL itself contains one;
for Harbor results, prefer `harbor-import --diagnose` so the verifier footprint
is joined with the agent trajectory.

## ATIF Trajectory Viewer

The local ATIF viewer at:

```text
/Users/hugo/Documents/terminal-bench-3.0-PR/ATIF-trajectory-viewer
```

already supports local bundle discovery through
`public/local/local-bundles.json`. Harness-TrajecDebug exports Harbor runs into
that format without modifying the viewer application code.

Inspect the viewer checkout:

```bash
PYTHONPATH=src python3 -m harness_trajecdebug.cli atif-viewer-info \
  --viewer-root /Users/hugo/Documents/terminal-bench-3.0-PR/ATIF-trajectory-viewer
```

Export a Harbor run or one trial into the viewer:

```bash
PYTHONPATH=src python3 -m harness_trajecdebug.cli atif-viewer-export \
  --run /path/to/harbor/runs/swebenchpro-fix-ansible-invalid-hosts-claude-code-kimi-k26 \
  --viewer-root /Users/hugo/Documents/terminal-bench-3.0-PR/ATIF-trajectory-viewer \
  --label swebenchpro-fix-ansible-invalid-hosts-claude-code-kimi-k26 \
  --diagnose
```

The exporter writes:

- `public/local/local-bundles.json`
- `public/local/runs/<label>/viewer-bundle.json`
- `public/local/runs/<label>/payloads/<runId>.json`
- `public/local/runs/<label>/normalized/<runId>.json`
- `public/local/runs/<label>/diagnoses/<runId>-diagnosis.json` when
  `--diagnose` is used

Payloads are clipped and API-token-like values are redacted before being placed
under the viewer's public directory.

## Harbor Registry Datasets

The local Harbor CLI can run registry-backed datasets, including
`swebenchpro@1.0`, directly with `harbor run -d`. The HTD runtime scripts can
read a Seed Anthropic-compatible route directly with
`--endpoint-profile seed-coding-plan`, which maps `SEED_CODING_PLAN_BASE_URL`
and `SEED_CODING_PLAN_API_KEY` into the Claude Code environment.

```bash
scripts/check_model_endpoint.py --endpoint-profile seed-coding-plan --model kimi-k2.6
scripts/run_candidate_kimi_reruns.sh --endpoint-profile seed-coding-plan
```

For raw Harbor commands outside the HTD wrappers, map the Seed variables to the
names Claude Code expects:

```bash
export ANTHROPIC_BASE_URL="${SEED_CODING_PLAN_BASE_URL}"
export ANTHROPIC_API_KEY="${SEED_CODING_PLAN_API_KEY}"

/opt/miniconda3/envs/terminal-bench/bin/harbor run \
  -d swebenchpro@1.0 \
  -t swebenchpro-fix-ansible-invalid-hosts \
  -a claude-code \
  -m kimi-k2.6 \
  --jobs-dir harbor/runs \
  --job-name swebenchpro-fix-ansible-invalid-hosts-claude-code-kimi-k26 \
  --n-concurrent 1 \
  --export-traces \
  --export-verifier-metadata
```
