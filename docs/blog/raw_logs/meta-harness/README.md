# Meta-Harness Raw Logs

This directory contains expanded raw evidence for the Meta-Harness blog notes in
[`../../meta-harness/`](../../meta-harness/README.md).

The evidence layout mirrors the original Harbor run identity:

```text
harbor_runs/<run-name>/<trial-id>/
```

For small baseline trials, the full trial directory is copied. For large Kimi
Code trials, the expanded evidence keeps the files needed to audit the claim:

- `result.json`, `config.json`, and `trial.log`;
- `agent/prompt.txt`, `agent/previous-failure.txt`, `agent/env-snapshot.txt`,
  `agent/kimi-stdout.txt`, `agent/kimi-stderr.txt`, and `agent/trajectory.json`;
- `agent/setup/checks.json` and upload/post-upload return-code files;
- task-specific final artifacts such as `run.py`, `server.py`,
  `.kimi-post-upload.sh`, `sol.sql`, or `secret.txt`;
- `verifier/ctrf.json`, `verifier/test-stdout.txt`, and `verifier/reward.txt`.

Large benchmark inputs and full third-party workspaces are intentionally not
duplicated here. The canonical sweep archives remain in
[`../../../case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/raw-logs/`](../../../case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/raw-logs/).

Benchmark fake credential literals in the `sanitize-git-repo` logs are
redacted to placeholder strings so the public PR is not blocked by secret
scanning. The surrounding prompts, trajectories, verifier failures, and reward
records are preserved.

## Included Runs

| Case | Run directories |
| --- | --- |
| `cancel-async-tasks` | `tb21-cancel-async-tasks-claude-code-k6`, `tb21-cancel-async-tasks-kimicode-4x` |
| `sanitize-git-repo` | `tb21-sanitize-git-repo-claude-code-k6`, `tb21-sanitize-kimicode-without-metaharness-fixed-20260610T153736`, `tb21-sanitize-kimicode-with-metaharness-20260610T154556` |
| `kv-store-grpc` | `tb21-kv-store-grpc-claude-code-k6`, `tb21-kvgrpc-kimicode-without-metaharness-20260610T155413`, `tb21-kvgrpc-kimicode-with-metaharness-20260610T155642` |
| `git-leak-recovery` | `tb21-git-leak-recovery-claude-code-k6`, `tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610` |
| `query-optimize` control | `tb21-query-optimize-claude-code-k6`, `tb21-queryopt-kimicode-without-metaharness-stop-20260610T171537`, `tb21-queryopt-kimicode-with-metaharness-stop-r2-20260610T174611` |

Checksums are recorded in [`checksums.sha256`](checksums.sha256).
