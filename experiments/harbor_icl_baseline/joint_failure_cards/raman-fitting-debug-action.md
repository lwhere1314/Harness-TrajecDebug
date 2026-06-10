# Harness-TrajecDebug Debug-Action Card: raman-fitting

## Source Signal

This card is synthesized from a failed Codex + GPT-5.5 trajectory and its
official verifier footprint. It is not a teacher-success replay.

The failed run reached artifact closure: `/app/results.json` existed, parsed as
JSON, and had the requested `G` / `2D` keys. The failure was process-level:
Codex explicitly committed to writing the result "using the raw instrument
x-coordinate" after inspecting `graphene.dat`.

The resulting artifact was on the wrong scale:

```text
G:  x0 around 16203, gamma around 232
2D: x0 around 33264, gamma around 1768
```

The verifier expected Raman-shift scale peaks instead: G around 1580 cm^-1 and
2D around 2700 cm^-1, both with narrow linewidths. So the bug was not missing
JSON closure; it was the earlier axis / window commitment.

## Critical Step

The decisive action is before fitting:

> Convert the first column of `graphene.dat` with `x = 1e7 / raw_x`, then crop
> the converted axis to the G and 2D windows before fitting.

Do not choose the largest raw-intensity peaks, and do not use raw x or raw x/10
as the reported `x0` scale.

## Action Boundary

Build `/app/results.json` around these constraints:

1. Parse `/app/graphene.dat` as two columns. The decimals use commas, so replace
   `,` with `.` before `float(...)`.
2. Convert the first column immediately:

   ```python
   x = 1e7 / raw_x
   ```

3. Select the G fitting window after conversion: `1500 < x < 1700`.
4. Select the 2D fitting window after conversion: `2500 < x < 2900`.
5. Fit each window with Lorentzian plus constant offset:

   ```python
   A * gamma**2 / ((x - x0)**2 + gamma**2) + offset
   ```

6. Use robust initial guesses around `x0=1580, gamma=10` for G and
   `x0=2700, gamma=10` for 2D.
7. Write `/app/results.json` with numeric `x0`, `gamma`, `amplitude`, and
   `offset` fields.

## Minimal Coding Plan

Use SciPy if available. If it is not installed, install `scipy` and `numpy` or
write a small least-squares/grid fit, but keep the same converted-axis windows.

```python
from scipy.optimize import curve_fit

def lorentzian(x, x0, gamma, A, offset):
    return A * gamma**2 / ((x - x0)**2 + gamma**2) + offset
```

The safe parse-and-fit skeleton is:

```python
rows = []
with open('/app/graphene.dat') as f:
    for line in f:
        if line.strip():
            a, b = line.split()[:2]
            rows.append((float(a.replace(',', '.')), float(b.replace(',', '.'))))

raw_x = np.array([r[0] for r in rows], dtype=float)
y = np.array([r[1] for r in rows], dtype=float)
x = 1e7 / raw_x
```

Then fit the two windows and serialize the result. Do not stop after checking
only that the JSON schema is valid; the failed trace already passed that check.

## Avoided Failure Patterns

Do not:

- fit the largest global raw peak;
- report `x0` values in raw instrument coordinates;
- divide raw x by 10 and treat that as Raman shift;
- validate only file existence / JSON parse / key names;
- use a broad full-spectrum fit where the large low-shift feature dominates the
  two target windows.

## Self-Check

After writing `/app/results.json`, run:

```bash
python - <<'PY'
import json, math
with open('/app/results.json') as f:
    data = json.load(f)
assert 1500 < data['G']['x0'] < 1700, data['G']
assert 2500 < data['2D']['x0'] < 2900, data['2D']
assert 1 < abs(data['G']['gamma']) < 50, data['G']
assert 1 < abs(data['2D']['gamma']) < 80, data['2D']
for peak in ['G', '2D']:
    for key in ['x0', 'gamma', 'amplitude', 'offset']:
        assert isinstance(data[peak][key], (int, float)) and math.isfinite(data[peak][key])
print('axis scale and artifact schema look safe')
PY
```

Then run the official verifier. The key repair is not a new output format; it
is the converted-axis fitting commitment.
