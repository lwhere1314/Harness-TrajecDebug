---
name: harness-runtime-icl
description: Run Harness-TrajecDebug runtime ICL canaries and compare no-TD versus with-TD evidence on Harbor or Terminal-Bench tasks.
type: prompt
---

# harness-runtime-icl

Load the canonical project skill at:

```text
plugins/harness-trajdebug-agent/skills/harness-runtime-icl/SKILL.md
```

If that file is present, follow it. If not, use `harness-trajdebug diagnose`, `harness-trajdebug harbor-import --diagnose`, and the scripts under `scripts/run_*icl*` to preserve raw trace evidence, verifier output, reward files, critical-step diagnosis, injected card paths, and artifact closure evidence.
