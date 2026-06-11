# Case Study: Meta-Harness on `git-leak-recovery`

`git-leak-recovery` is useful as an operational repair example: the Meta-Harness
rerun recovered the lost secret, wrote `/app/secret.txt`, cleaned reachable and
unreachable Git objects, and passed the official verifier.

This is not the cleanest strategy-only causal case because the original
`claude-code + kimi-k2.6` baseline failure also contains infrastructure noise
around verifier dependency download. The strong claim here is narrower: the
Meta-Harness run produced a verifier-clean final state, and the raw trajectory
shows how it got there.

Raw logs for this case are under
[`../raw_logs/meta-harness/harbor_runs/`](../raw_logs/meta-harness/harbor_runs/).

## Task

The task says a secret was accidentally committed under `/app/repo` and later
removed by rewriting history. The agent must:

- recover the single `secret[...]` value and write it to `/app/secret.txt`;
- clean the repository so the secret cannot be found anywhere in reachable or
  unreachable Git objects;
- leave irrelevant files and commit messages untouched.

## Conditions

| Condition | Trial | Result |
| --- | --- | --- |
| Claude Code + `kimi-k2.6` baseline | `git-leak-recovery__QihhiXn` | reward `0.0` |
| Kimi Code with Meta-Harness rerun | `git-leak-recovery__UkE8Koj` | reward `1.0`; 5 passed / 0 failed |

The baseline result records reward `0.0`:
[`result.json` L65-L66](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-claude-code-k6/git-leak-recovery__QihhiXn/result.json#L65-L66).

## What Meta-Harness Added

The Meta-Harness prompt carried the original task, the environment snapshot, and
the prior failure brief into the Kimi Code run:
[`prompt.txt` L31-L41](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610/git-leak-recovery__UkE8Koj/agent/prompt.txt#L31-L41).

The repair brief also preserved the prior verifier tail, including the `uv`
download failure:
[`previous-failure.txt` L26-L87](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610/git-leak-recovery__UkE8Koj/agent/previous-failure.txt#L26-L87).

## Trajectory

The Kimi Code trajectory first inspects the repository and finds the dangling
commit containing the secret:
[`kimi-stdout.txt` L9-L12](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610/git-leak-recovery__UkE8Koj/agent/kimi-stdout.txt#L9-L12).

It then writes `/app/secret.txt`, removes the dangling secret blob/commit/tree,
clears reflog/`ORIG_HEAD`, runs `git gc --prune=now`, and checks that no secret
string remains in Git storage:
[`kimi-stdout.txt` L25-L32](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610/git-leak-recovery__UkE8Koj/agent/kimi-stdout.txt#L25-L32).

The recovered final artifact is preserved here:
[`secret.txt`](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610/git-leak-recovery__UkE8Koj/agent/host-workspace/secret.txt).

## Verifier Result

The official verifier passed all five checks, including `test_no_secrets_in_commits`
and `test_no_secrets_in_unreachable_objects`:
[`ctrf.json` L9-L10](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610/git-leak-recovery__UkE8Koj/verifier/ctrf.json#L9-L10),
[`ctrf.json` L28-L47](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610/git-leak-recovery__UkE8Koj/verifier/ctrf.json#L28-L47).

The stdout summary confirms `5 passed`:
[`test-stdout.txt` L63-L67](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610/git-leak-recovery__UkE8Koj/verifier/test-stdout.txt#L63-L67).

The reward file records reward `1.0`:
[`result.json` L82-L83](../raw_logs/meta-harness/harbor_runs/tb21-git-leak-recovery-kimicode-with-metaharness-mhharbor-tmpcwd-20260611T133610/git-leak-recovery__UkE8Koj/result.json#L82-L83).

## Takeaway

Use this as a verified repair example, not the main causal proof. It shows that
the Meta-Harness/Kimi Code setup can recover a failed task into a clean Harbor
verifier pass, and that the raw trajectory is detailed enough to audit the
artifact and repository-cleanup steps.
