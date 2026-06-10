# Oracle-Grounded Critical-Step Card: raman-fitting

## Oracle Ground Truth Signal

The oracle-level signal is not "fit the two largest raw peaks." It is:

- parse `/app/graphene.dat` as two tab-separated columns with comma decimal
  separators;
- treat the first column as a wavelength-like / instrument axis, then convert
  it before any peak search with `shift_cm = 1e7 / raw_x`;
- crop the converted axis to the G and 2D Raman windows;
- fit each cropped window with a Lorentzian plus constant offset;
- write only `/app/results.json` with the required `G` and `2D` keys.

So the critical step is an axis-framing decision:

> Convert the spectrum to Raman-shift units before selecting the G and 2D
> fitting windows.

## Corrective Direction

Do not rank global raw-intensity maxima as the target peaks. The largest raw
feature can live outside the verifier's G / 2D windows after conversion, so a
"top peaks in raw x" plan can produce a valid JSON artifact with numerically
wrong parameters.

Use the oracle as a ground-truth process boundary:

1. Read the data from `/app/graphene.dat`.
2. Replace comma decimal separators with dots, then parse two numeric columns.
3. Compute `x = 1e7 / raw_x` before windowing.
4. Fit the G peak only on `1500 < x < 1700`.
5. Fit the 2D peak only on `2500 < x < 2900`.
6. Use the Lorentzian form:

   ```python
   y = A * gamma**2 / ((x - x0)**2 + gamma**2) + offset
   ```

7. Use initial guesses near `x0=1580, gamma=10` for G and
   `x0=2700, gamma=10` for 2D.
8. Write `/app/results.json` with numeric `x0`, `gamma`, `amplitude`, and
   `offset` values for both peaks.

## Minimal Coding Plan

Implement the solution as a small Python script. If SciPy is available or can
be installed, use `scipy.optimize.curve_fit` directly:

```python
import json
import numpy as np
from scipy.optimize import curve_fit

def lorentzian(x, x0, gamma, A, offset):
    return A * (gamma**2) / ((x - x0)**2 + gamma**2) + offset

def fit_window(x, y, lo, hi, x0_guess):
    mask = (x > lo) & (x < hi)
    xw = x[mask]
    yw = y[mask]
    p0 = [x0_guess, 10.0, float(yw.max() - yw.min()), float(yw.min())]
    params, _ = curve_fit(lorentzian, xw, yw, p0=p0, maxfev=20000)
    return params

rows = []
with open("/app/graphene.dat", "r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        a, b = line.strip().split()[:2]
        rows.append((float(a.replace(",", ".")), float(b.replace(",", "."))))

data = np.array(rows, dtype=float)
raw_x = data[:, 0]
y = data[:, 1]
x = 1e7 / raw_x

g = fit_window(x, y, 1500, 1700, 1580)
d2 = fit_window(x, y, 2500, 2900, 2700)

result = {
    "G": {
        "x0": float(g[0]),
        "gamma": float(g[1]),
        "amplitude": float(g[2]),
        "offset": float(g[3]),
    },
    "2D": {
        "x0": float(d2[0]),
        "gamma": float(d2[1]),
        "amplitude": float(d2[2]),
        "offset": float(d2[3]),
    },
}

with open("/app/results.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)
    f.write("\n")
```

## Critical Verifier Gates

The verifier has three independent gates:

- `/app/results.json` must exist and parse as JSON.
- The `G` entry must have parameters on the converted Raman-shift scale, around
  the 1580 cm^-1 band with a narrow linewidth.
- The `2D` entry must have parameters on the converted Raman-shift scale, around
  the 2700 cm^-1 band with a narrow linewidth.

Passing the JSON schema while fitting raw x coordinates is still a failure.

## Closure Check

Before finishing, inspect the generated JSON:

```bash
python - <<'PY'
import json, math
with open('/app/results.json') as f:
    data = json.load(f)
for peak in ['G', '2D']:
    assert set(data[peak]) == {'x0', 'gamma', 'amplitude', 'offset'}
    for key, value in data[peak].items():
        assert isinstance(value, (int, float)) and math.isfinite(value), (peak, key, value)
assert 1500 < data['G']['x0'] < 1700
assert 2500 < data['2D']['x0'] < 2900
print('converted-axis Raman peak fit looks plausible')
PY
```

Then run the official verifier. The local check only guards the common
critical-step failure: fitting the wrong x-axis scale.
