# One-Click Query-Optimize Reproduction

This is the shortest reproducible path for the `harness-runtime-icl` skill and
the `query-optimize` runtime Debug-Action case.

## 1. Clone And Install

```bash
git clone https://github.com/lwhere1314/Harness-TrajecDebug.git
cd Harness-TrajecDebug
python3 -m pip install -e .
bash scripts/install_harness_runtime_icl_skill.sh
```

Restart Codex, or open a new Codex thread, so the local skill registry reloads.

## 2. Configure One Endpoint

Use any endpoint profile supported by `scripts/lib_endpoint_profile.sh`.

For Ark-compatible Kimi:

```bash
export ARK_API_KEY="..."
export ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/coding"
```

For a Seed coding-plan proxy:

```bash
export SEED_CODING_PLAN_API_KEY="..."
export SEED_CODING_PLAN_BASE_URL="..."
```

Do not commit these values. The runner only records which profile was used.

## 3. Dry-Run First

```bash
bash scripts/reproduce_query_optimize_skill.sh \
  --endpoint-profile ark \
  --model kimi-k2.6
```

Dry-run performs endpoint preflight and controller replay, but does not launch
the Harbor task.

## 4. Full Reproduction

```bash
bash scripts/reproduce_query_optimize_skill.sh \
  --endpoint-profile ark \
  --model kimi-k2.6 \
  --run
```

By default the script runs both controlled conditions:

- `debug_action + sdk_live`
- `outcome_only + sdk_live`

Both use `query-optimize`, `kimi-k2.6`, `sdk_live`, and the same first `Bash`
tool boundary. The expected mechanism check is:

| Variant | Expected result |
| --- | --- |
| `debug_action + sdk_live` | passes the verifier when the card provides the concrete `/app/sol.sql` repair action and stop rule |
| `outcome_only + sdk_live` | injects at the same boundary but usually fails or times out because it lacks the repair action |

The script prints the raw log directory and a compact summary. Each trial also
contains `agent/sdk-live-events.jsonl`, verifier outputs, `result.json`, and
`sdk-live-summary.json`.

## Codex Prompt

After installing the skill, another Codex user can simply ask:

```text
Use the harness-runtime-icl skill and run the query-optimize one-click
reproduction with sdk_live. Dry-run first; if preflight passes, run both
debug_action and outcome_only variants and summarize the raw log paths.
```
