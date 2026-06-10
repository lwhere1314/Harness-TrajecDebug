#!/usr/bin/env bash
set -euo pipefail

cd /Users/hugo/Projects/Harness-TrajecDebug

export PYTHONPATH=/Users/hugo/Projects/Harness-TrajecDebug
export PATH="/Users/hugo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:${PATH}"

TASK_PATH=/Users/hugo/.cache/harbor/tasks/5pwPaf92MGZBJjvqnuBn9d/cancel-async-tasks
NODE_BIN=/Users/hugo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
KIMI_CODE_ROOT=/Users/hugo/Projects/Harness-TrajecDebug/kimi-code
AGENT_IMPORT=harbor_adapters.kimi_code_host_agent:KimiCodeHostAgent
PREVIOUS_FAILURE=/Users/hugo/Projects/Harness-TrajecDebug/harbor_adapters/cancel_async_tasks_previous_failure.txt

/opt/miniconda3/envs/terminal-bench/bin/harbor run \
  --job-name cancel-async-tasks-without-metaharness-4x \
  --jobs-dir harbor/runs \
  -n 1 \
  --n-attempts 4 \
  --force-build \
  --agent-import-path "${AGENT_IMPORT}" \
  --model kimi-for-coding \
  --ak kimi_code_root="${KIMI_CODE_ROOT}" \
  --ak node_bin="${NODE_BIN}" \
  --ak prompt_timeout_sec=900 \
  --ak include_env_snapshot=false \
  --path "${TASK_PATH}"

/opt/miniconda3/envs/terminal-bench/bin/harbor run \
  --job-name cancel-async-tasks-with-metaharness-4x \
  --jobs-dir harbor/runs \
  -n 1 \
  --n-attempts 4 \
  --force-build \
  --agent-import-path "${AGENT_IMPORT}" \
  --model kimi-for-coding \
  --ak kimi_code_root="${KIMI_CODE_ROOT}" \
  --ak node_bin="${NODE_BIN}" \
  --ak prompt_timeout_sec=900 \
  --ak previous_failure_path="${PREVIOUS_FAILURE}" \
  --ak include_env_snapshot=true \
  --path "${TASK_PATH}"
