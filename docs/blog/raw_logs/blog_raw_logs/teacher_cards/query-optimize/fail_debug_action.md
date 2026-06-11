# Failure-Derived Debug-Action Card: query-optimize

This card is synthesized from a failed same-task trajectory and its verifier
footprint. It is not copied from a passing teacher artifact and does not contain
a ready-made `/app/sol.sql` heredoc. Use it as failure-derived repair guidance.

## Reference view

You are given the Open English Wordnet (OEWN) database in SQLite format at
`/app/oewn.sqlite`. The original query is in `/app/my-sql-query.sql`. Write one
SQLite query to `/app/sol.sql`; it must preserve the exact output, contain no
comments, be terminated by one semicolon, and must not modify the database.

## Failed teacher outcome

Task: query-optimize
Teacher outcome: reward=0.0
Verifier summary: tests=6, passed=5, failed=1
Failed gate: `test_compare_golden_vs_solution_runtime`

The failed teacher produced a semantically correct rewrite, but the official
runtime benchmark still failed:

- golden median: `0.3556585449987324`
- failed solution median: `0.5464121470031387`
- speedup solution vs golden: `0.6508979475463408`

## Critical step

Pattern: `budget debt loop`

The failed trajectory correctly removed the obvious correlated scalar
subqueries, but it then promoted a global `ROW_NUMBER()` ranking route over
per-word/per-synset groups. That route matched the original output but still
spent too much work before the final `LIMIT 500`, so it failed the runtime gate.

## Recommended next action

Before writing `/app/sol.sql`, inspect `/app/my-sql-query.sql` and the schema,
then use this repair route:

1. Build one grouped CTE for `(wordid, synsetid)` sense counts and joined
   `domainid` / `posid`.
2. Compute candidate word stats from that grouped CTE.
3. Order candidate words by the verifier order and limit to 500 before doing
   remaining top-synset work.
4. Avoid a global `ROW_NUMBER()` window over all word/synset groups. For the
   top synset, use an aggregate tie-break key such as
   `(1000000 - sense_count) * 1000000 + synsetid`, then decode it in the final
   projection.
5. Write `/app/sol.sql` only after the query has the exact required columns:
   `word_id`, `word`, `total_synsets`, `total_senses`, `distinct_domains`,
   `distinct_posids`, `top_synsetid`, `top_synset_sense_count`.

## Closure checks

- `/app/sol.sql` exists.
- It is one `WITH` or `SELECT` statement, no comments, one semicolon.
- It does not modify `/app/oewn.sqlite`.
- Its output matches `/app/my-sql-query.sql` exactly.
- Runtime must beat the official threshold, not merely improve over the
  original query. If the solution is around `0.55s` median on this verifier,
  treat it as still failed.

## Stop rule

Once `/app/sol.sql` is written and a cheap equivalence/performance smoke check
passes, stop and let the official verifier grade it.
