# Harness-TrajecDebug Debug-Action Card V2: cli-2ph-simplex

Use this as the next CLI repair card. The previous card was too broad. This
card is based on a concrete minimal probe against the failed with-TD artifact.

Observed critical error step:

- Minimal case `ge_bound_respected`:
  `max x1 + 5*x2`, constraints `x1+2*x2 <= 40`,
  `2*x1+x2 >= 39`, `x1+x2 = 20`, expected objective `24`.
- The submitted solver raised `Exception: Unbounded` even though this LP is
  bounded and feasible.
- Tracing the submitted code showed the first wrong transition in
  `simplex/tableau.py::build_initial_tableau`: artificial columns are initialized
  in the Phase 1 objective with `-1.0`. The verifier/reference construction uses
  `+1.0` for artificial variables, then canonicalizes by subtracting the
  artificial-basic rows. With `-1.0`, the initial Phase 1 objective row becomes
  `[Z=1, x1=3, x2=2, s2=-1, RHS=59]`; the solver then misclassifies Phase 1 as
  unbounded before finding a feasible basis.

Verified repair evidence:

- In a temporary copy, changing only `data[obj_row][artificial_col]` from
  `-1.0` to `+1.0` made `ge_bound_respected` return objective `24.0`.
- The same one-line fix made `fractional_primal_from_mixed_basis` return
  objective `11.0`.
- Full test count improved from `63 failed / 40 passed` to
  `12 failed / 91 passed` in the temporary probe.

Critical actions, in order:

1. Fix Phase 1 objective sign first:
   artificial variable reduced costs must start as `+1.0`, then canonicalize
   with the current artificial basis. Do not proceed to other rewrites until
   `ge_bound_respected` no longer raises `Unbounded`.
2. After Phase 1 terminates, explicitly inspect the Phase 1 objective RHS.
   If the auxiliary optimum is nonzero, this is infeasible; per prompt, return
   the best-effort last tableau and write output files. Do not enter Phase 2 and
   do not raise `Unbounded` for infeasible cases.
3. Fix problem-report rounding with `Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP)`.
   The current `math.floor(n*100+0.5)` is wrong for `1.005`, `-1.005`,
   `-2.995`, and negative zero. Values rounding to zero must render as positive
   `0.00`.
4. Fix malformed literal handling: parse CLI literals inside the main `try`
   block after `parse_args`, not via `argparse type=...`, so malformed literals
   produce a normal Python traceback on stderr and no partial output files.
5. For `--initial_pivots`, the shortest path requirement is global over the
   whole continuation, not separately shortest Phase 1 plus separately shortest
   Phase 2. The current `minimal_pivot_path(phase1)` followed by
   `minimal_pivot_path(phase2)` fails cases like raw row 4 (`4` pivots emitted,
   expected max `3`). Search over valid continuations with the phase transition
   included, or otherwise choose a Phase 1 continuation that minimizes total
   logged pivots through final Phase 2 optimum.

Closure checks:

- First run the two minimal probes:
  `ge_bound_respected` must return objective `24.0`; `fractional_primal_from_mixed_basis`
  must return objective `11.0`.
- Then run `pytest -q /tests/test_outputs.py`.
- Do not stop at fewer failures; reward requires all verifier tests to pass.
