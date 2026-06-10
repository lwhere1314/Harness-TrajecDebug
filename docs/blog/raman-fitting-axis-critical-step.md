# Case Study: Axis-Transform Critical Step on `raman-fitting`

This case study records a Codex-failed critical-step lifting result for
Harness-TrajecDebug.

It is not a clean joint-failure case like `sam-cell-seg`: the historical Kimi
side had verifier infrastructure noise rather than a useful model-quality
failure footprint. The useful signal here came from a failed Codex + GPT-5.5
run that reached artifact closure but committed to the wrong x-axis scale.

```text
Codex + GPT-5.5 failed: schema-valid JSON, raw-axis peak parameters
HTD diagnosis:          wrong axis / window commitment before fitting
Debug-Action card:      convert x = 1e7 / raw_x, then fit G and 2D windows
Rerun:                  Claude Code + kimi-k2.6 reward 1.0, 3/3 tests passed
```

## Task

`raman-fitting` asks the agent to fit the G and 2D peaks in
`/app/graphene.dat` and write `/app/results.json`:

```json
{
  "G": {"x0": 0, "gamma": 0, "amplitude": 0, "offset": 0},
  "2D": {"x0": 0, "gamma": 0, "amplitude": 0, "offset": 0}
}
```

The data file is a two-column spectrum with tab separation and comma decimal
separators. The hidden critical detail is that the first column must be
converted before peak selection:

```python
x = 1e7 / raw_x
```

Only after this conversion should the agent crop the G and 2D Raman windows and
fit a Lorentzian plus constant offset.

## Historical Failure

The Codex + GPT-5.5 trace did not fail because it forgot the artifact. It wrote
`/app/results.json`, and the JSON schema was valid. The failure came earlier:
after inspecting the spectrum, the agent explicitly decided to write the result
using the raw instrument x-coordinate.

The terminal footprint was clear:

```text
PASSED test_result_file_exists
FAILED test_G_Peak
FAILED test_2D_Peak
```

The produced `x0` values were around `16203` and `33264`, which are raw-axis
scale values. The verifier expected the Raman-shift scale, around the G band
near `1580 cm^-1` and the 2D band near `2700 cm^-1`.

Harness-TrajecDebug therefore labels the critical step as:

> Convert the first column with `x = 1e7 / raw_x`, then crop the converted axis
> to the G and 2D windows before fitting.

## HTD Diagnosis

In reference/state/commitment terms:

| View | Evidence |
| --- | --- |
| Reference | final artifact is `/app/results.json`; G and 2D parameters must be on Raman-shift scale |
| State | the run produced valid JSON, but the fitted parameters were on raw x scale |
| Commitment | the agent chose to fit and report raw instrument x-coordinates |
| Footprint | `test_G_Peak` and `test_2D_Peak` failed while artifact existence passed |
| Counterfactual | converting `raw_x` before windowing makes the same Lorentzian fit pass |

This is exactly the kind of failure that outcome-only reward hides. Reward `0`
does not distinguish "no JSON file" from "schema-valid artifact, wrong
coordinate system." The second failure is much more actionable.

## Stage A: Oracle-Grounded Card

The oracle-grounded card used the oracle only to define the process boundary:

1. parse comma-decimal tab-separated data;
2. compute `x = 1e7 / raw_x`;
3. fit only `1500 < x < 1700` for G;
4. fit only `2500 < x < 2900` for 2D;
5. use a Lorentzian plus constant offset;
6. write `/app/results.json`.

Result:

```text
trial: runs/harbor_icl_baseline/harbor_runs_oracle_grounded/
  htd-dynamic-icl-prelude-oracle_grounded-raman-fitting-kimi-k2-6/
    raman-fitting__MjbR2nV

inject_mode = prelude
context_variant = oracle_grounded
target = Claude Code + kimi-k2.6
reward = 1.0
verifier = 3/3 tests passed
```

This confirmed that the task copy, verifier, endpoint, and corrective framing
were all executable.

## Stage B: Oracle-Free Debug-Action

The Debug-Action card removed oracle access and used only the failed Codex trace
signal:

- artifact closure was already solved;
- the bad commitment was raw-axis fitting;
- the repair boundary was axis conversion before windowing.

Result:

```text
trial: runs/harbor_icl_baseline/harbor_runs_joint_failure/
  htd-dynamic-icl-prelude-debug_action-raman-fitting-kimi-k2-6/
    raman-fitting__RFdou7e

inject_mode = prelude
context_variant = debug_action
target = Claude Code + kimi-k2.6
reward = 1.0
verifier = 3/3 tests passed
```

The agent trace shows the injected card changed the first decisive action. The
run parsed the file, converted the x-axis, cropped the two windows, fitted with
`scipy.optimize.curve_fit`, self-checked the result, and then passed:

```text
PASSED test_result_file_exists
PASSED test_G_Peak
PASSED test_2D_Peak
```

## Why This Case Matters

This is a narrower result than complementary joint-failure lifting, but it is a
good mechanism check for the "left foot steps on right foot" idea:

- a strong teacher run failed;
- the failure still contained a clear evidence-grounded critical step;
- Harness-TrajecDebug converted that footprint into a bounded repair hint;
- Claude Code + `kimi-k2.6` executed the repair and passed.

The case should still be reported as same-task repair, not held-out
generalization. Its value is that it demonstrates process evidence can be
useful even when the teacher trajectory itself is not successful.
