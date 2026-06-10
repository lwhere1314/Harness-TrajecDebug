# Harness-TrajecDebug Debug-Action Card: sanitize-git-repo

## Source Signal

This card is synthesized from two failed trajectories, not from an oracle
solution:

- Claude Code + Kimi-k2.6 failed because it cleaned the obvious files but left a
  second HuggingFace token occurrence embedded inside the JSON dataset metadata
  diff/setup commands.
- Codex + GPT-5.5 failed because it rewrote or garbage-collected git history;
  the verifier then could not resolve the original reference commit used for
  the "no other files changed" check.

## Critical Step

The task is not "purge all secrets from all git history." The binding
constraint is: edit only the contaminated working-tree files, replace every
secret-shaped value with the exact placeholders from the instruction, and keep
the original git object graph/reference commit available.

## Action Boundary

Do not run any command that mutates repository history or refs:

- no `git filter-branch`
- no `git filter-repo`
- no `git rebase`
- no `git reset --hard`
- no new commit
- no `git gc`, `git prune`, or `git reflog expire`
- no deleting `.git`

Only edit these three files:

- `/app/dclm/ray_processing/ray_cluster.yaml`
- `/app/dclm/ray_processing/process.py`
- `/app/dclm/exp_data/datasets/tokenized/rw_v2_fasttext_openhermes_vs_rw_v2_bigram_0.1_arcade100k.json`

## Replacement Checklist

In those three files, replace every occurrence of these patterns, including
tokens embedded inside JSON strings, escaped diffs, setup commands, and lowercase
copies:

- `AKIA[0-9A-Z]{16}` -> `<your-aws-access-key-id>`
- any value assigned/exported as `AWS_SECRET_ACCESS_KEY` -> `<your-aws-secret-access-key>`
- `gh[pousr]_[A-Za-z0-9]{20,}` -> `<your-github-token>`
- `hf_[A-Za-z0-9]{29,}` -> `<your-huggingface-token>`

The second HuggingFace token occurrence inside the large JSON file is easy to
miss. Search the final edited file for `hf_` before finishing.

## Self-Check

Before final answer, verify:

```bash
cd /app/dclm
git diff --name-only d6987af002b122fef54bc0be402062c76488a4d9 -- \
  | sort
```

The output should contain exactly the three contaminated paths above. Then run
grep checks over those files to confirm no AWS key id, GitHub token, or
HuggingFace token pattern remains.

