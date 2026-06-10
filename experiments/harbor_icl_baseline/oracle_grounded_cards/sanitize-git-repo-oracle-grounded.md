# Oracle-Grounded Critical-Step Card: sanitize-git-repo

## Oracle Ground Truth Signal

The oracle solution does not rewrite repository history. Its structure is:

- search the working tree for secret-shaped values;
- exclude `.git`;
- replace only secret-shaped strings with the requested placeholders;
- leave the repository history and reference commit intact.

So the critical step is a task-framing decision:

> Treat this as a bounded working-tree sanitization task, not as a full
> history-purge task.

## Corrective Direction

Use the oracle as a ground-truth constraint on the repair path:

1. Work inside `/app/dclm`.
2. Do not mutate git history, refs, reflogs, or object storage.
3. Replace secret-shaped values in tracked working-tree files only.
4. Preserve the placeholder text exactly as requested by the task prompt.
5. Verify that no unrelated file changed relative to the original reference
   commit.

## Forbidden Actions

Do not run:

- `git filter-branch`
- `git filter-repo`
- `git rebase`
- `git reset --hard`
- `git gc`
- `git prune`
- `git reflog expire`
- `rm -rf .git`

These actions can remove or rewrite the reference commit that the verifier uses
to check whether unrelated files changed.

## Search Targets

Search the working tree for these classes of values:

- AWS access key ids: `AKIA[0-9A-Z]{16}`
- AWS secret values assigned/exported through `AWS_SECRET_ACCESS_KEY`
- GitHub tokens: `gh[pousr]_[A-Za-z0-9]{20,}`
- HuggingFace tokens: `hf_[A-Za-z0-9]{29,}`

Be careful with large JSON files. A token may be embedded inside a serialized
diff or setup-command string rather than appearing as a normal config field.

## Replacement Targets

Use the exact placeholders from the task:

- `<your-aws-access-key-id>`
- `<your-aws-secret-access-key>`
- `<your-github-token>`
- `<your-huggingface-token>`

## Closure Check

Before finishing, run a local check equivalent to:

```bash
cd /app/dclm
git diff --name-only d6987af002b122fef54bc0be402062c76488a4d9 -- | sort
```

The changed-file list should contain only files that actually held secret values.
Then grep the edited files for the token patterns above. The goal is not to
make the repo look clean by deleting history; the goal is to make the working
tree match the sanitized reference while preserving the verifier's reference
commit.

