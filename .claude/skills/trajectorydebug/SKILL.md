---
name: trajectorydebug
description: Use Harness-TrajecDebug to diagnose terminal-agent trajectories, compare no-TD versus with-TD runs, build Debug-Action cards, and run Harbor or Terminal-Bench runtime ICL canaries.
type: prompt
---

# trajectorydebug

Load the canonical project skill at:

```text
plugins/harness-trajdebug-agent/skills/trajectorydebug/SKILL.md
```

If that file is present, follow it. If not, use `harness-trajdebug diagnose`, `harness-trajdebug harbor-import --diagnose`, and the scripts under `scripts/run_*icl*` to preserve raw trace evidence, verifier output, reward files, critical-step diagnosis, injected card paths, and artifact closure evidence.
