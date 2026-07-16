# Repository architecture and release boundaries

Harness-TrajecDebug keeps research evidence in the same repository so claims
remain auditable, but that evidence is not part of the Python distribution.

## Layers

| Layer | Paths | Release behavior |
| --- | --- | --- |
| Installable library and CLI | `src/harness_trajecdebug/` | Included in wheel and source distribution. |
| Agent integrations | `plugins/`, `.agents/`, `.claude/`, `.kimi-code/` | Used directly from a repository checkout; not included in Python packages. |
| Reproducible examples and runners | `demo/`, `examples/`, `scripts/` | Development and integration surface; not included in Python packages. |
| Research evidence | `docs/case-studies/`, `docs/blog/raw_logs/`, `experiments/` | Retained for audit and reproduction; never included in Python packages. |

The `src/harness_trajecdebug/experiments/` namespace is Python orchestration
code used by the CLI and is distinct from top-level `experiments/`, which holds
run artifacts and protocols.

## Artifact policy

- Raw evidence stays under `docs/**/raw-logs`, `docs/**/raw_logs`, or
  top-level `experiments/`, next to its report or protocol.
- Large archives and videos are Git LFS objects. `.gitattributes` is the
  authoritative mapping.
- A normal Python release must stay below 2 MB per archive and must not contain
  repository research assets.
- `scripts/check_repository_boundaries.py` enforces LFS coverage for tracked
  large blobs and known binary evidence types.
- `scripts/check_distribution_contents.py` inspects built wheels and source
  distributions; CI runs both checks on every push and pull request.

Build release artifacts with:

```bash
python3 -m pip install build==1.2.2.post1
python3 -m build
python3 scripts/check_distribution_contents.py dist/*
```
