# Case Study: Meta-Harness on `sanitize-git-repo`

`sanitize-git-repo` is a good example of a repair brief improving precision.
The failed runs knew the repository contained fake credentials, but the verifier
was stricter than "remove obvious secrets": it required exact replacements in
three contaminated files and required the original comparison commit to remain
resolvable.

Raw logs for this case are under
[`../raw_logs/meta-harness/harbor_runs/`](../raw_logs/meta-harness/harbor_runs/).

## Task

The task asks the agent to sanitize a repository under `/app/dclm`. The verifier
checks three contaminated files, verifies token-shaped values are replaced with
the expected placeholders, compares the edited files byte-for-byte against
expected versions, and checks that no unrelated files changed.

## Conditions

| Condition | Trial | Result |
| --- | --- | --- |
| Claude Code + `kimi-k2.6` baseline | `sanitize-git-repo__FbeDTPh` | reward `0.0`; 1 passed / 2 failed |
| Kimi Code without Meta-Harness | `sanitize-git-repo__eMzBpYn` | reward `0.0`; 0 passed / 3 failed |
| Kimi Code with Meta-Harness | `sanitize-git-repo__27w76Zf` | reward `1.0`; 3 passed / 0 failed |

## What Failed Before

The Claude Code baseline failed both the removal check and the exact replacement
check:
[`ctrf.json` L9-L10](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-git-repo-claude-code-k6/sanitize-git-repo__FbeDTPh/verifier/ctrf.json#L9-L10),
[`ctrf.json` L19-L40](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-git-repo-claude-code-k6/sanitize-git-repo__FbeDTPh/verifier/ctrf.json#L19-L40).

The Kimi Code without-Meta-Harness run failed all three checks. It also broke the
Git comparison base: the verifier could not resolve commit
`d6987af002b122fef54bc0be402062c76488a4d9`:
[`test-stdout.txt` L167-L175](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-kimicode-without-metaharness-fixed-20260610T153736/sanitize-git-repo__eMzBpYn/verifier/test-stdout.txt#L167-L175).

## What Meta-Harness Added

The Meta-Harness repair brief named the exact verifier contract and the failure
mode. It told the agent to edit only three paths, replace every AWS/GitHub/HF
token-shaped value, preserve JSON escaping, and avoid history-rewriting tools
because the verifier needs the comparison commit to remain resolvable:
[`previous-failure.txt` L12-L24](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-kimicode-with-metaharness-20260610T154556/sanitize-git-repo__27w76Zf/agent/previous-failure.txt#L12-L24),
[`previous-failure.txt` L34-L50](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-kimicode-with-metaharness-20260610T154556/sanitize-git-repo__27w76Zf/agent/previous-failure.txt#L34-L50).

The key guidance was that one contaminated JSON file contains a stringified
patch. The missed token was inside escaped text, so a shallow edit could pass a
visual spot-check and still fail the official verifier.

## Trajectory Shift

| Without Meta-Harness | With Meta-Harness |
| --- | --- |
| Sanitizes obvious values but leaves the final state inconsistent with the verifier's exact expected files and Git comparison base. | Uses the repair brief to constrain edits to the three expected files, search nested/escaped token text, and preserve the commit needed by the verifier. |

The with-Meta-Harness prompt and trajectory are preserved here:
[`prompt.txt`](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-kimicode-with-metaharness-20260610T154556/sanitize-git-repo__27w76Zf/agent/prompt.txt),
[`trajectory.json`](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-kimicode-with-metaharness-20260610T154556/sanitize-git-repo__27w76Zf/agent/trajectory.json).

## Verifier Result

The Meta-Harness run passed all three official tests:
[`ctrf.json` L9-L10](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-kimicode-with-metaharness-20260610T154556/sanitize-git-repo__27w76Zf/verifier/ctrf.json#L9-L10),
[`ctrf.json` L19-L38](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-kimicode-with-metaharness-20260610T154556/sanitize-git-repo__27w76Zf/verifier/ctrf.json#L19-L38).

The reward file records reward `1.0`:
[`result.json` L79-L80](../raw_logs/meta-harness/harbor_runs/tb21-sanitize-kimicode-with-metaharness-20260610T154556/sanitize-git-repo__27w76Zf/result.json#L79-L80).

## Takeaway

This case shows Meta-Harness helping with verifier-shaped precision. The useful
signal was not generic "remove secrets"; it was the exact failure contract:
three files only, escaped nested token text included, and no history rewrite that
breaks the verifier's Git diff base.
