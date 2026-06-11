# Meta-Harness Repair Brief: largest-eigenval

## Source failure

- Harness: Harbor / Terminal-Bench 2.1 proxy task
- Source task: `largest-eigenval`
- Prior agent: `claude-code`
- Prior model: `kimi-k2.6`
- Prior run: `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy/jobs/tb21-largest-eigenval-claude-code-k6`
- Prior reward: `0`

## Official verifier contract

Implement `find_dominant_eigenvalue_and_eigenvector(A)` in `/app/eigen.py`.
The input is a real `np.float64` square matrix up to `10x10`, and it may have a
complex dominant eigenpair. The return value must satisfy:

- `A @ eigenvec` is close to `eigenval * eigenvec`;
- `abs(eigenval)` is equal to the largest eigenvalue magnitude;
- median runtime is faster than the verifier reference, which calls
  `np.linalg.eig(A)`, selects `np.argmax(np.abs(eigenvalues))`, and returns the
  matching eigenvector.

The hidden verifier tested sizes `2..10` and timed 100 random matrices per size
in an isolated process.

## What went wrong previously

The prior K2.6 candidate left `/app/eigen.py` essentially identical to the
reference:

```python
eigenvalues, eigenvectors = np.linalg.eig(A)
idx = np.argmax(np.abs(eigenvalues))
return eigenvalues[idx], eigenvectors[:, idx]
```

Correctness passed, but speedup failed on odd sizes:

- `5x5`: candidate median `0.000011` s, reference median `0.000011` s;
- `7x7`: candidate median `0.000017` s, reference median `0.000017` s;
- `9x9`: candidate median `0.000021` s, reference median `0.000020` s.

The run also ended with `AgentTimeoutError`, but the verifier produced a normal
reward file and test stdout. Treat the actionable failure as "repeated the
reference too closely and did not create a consistent speed advantage."

## Repair guidance

- Do not submit a wrapper around `np.linalg.eig(A)` that performs the same work
  as the reference.
- Any shortcut must still handle non-symmetric real matrices and complex
  dominant eigenpairs.
- The verifier captures references to `np.linalg.eig` and `np.linalg.eigvals`
  before importing candidate code, so monkeypatching NumPy is not a valid path.
- Focus on reducing per-call overhead or computing only the dominant pair. If a
  fallback to `np.linalg.eig` is used, it must be rare enough that the median
  timing still beats the reference for each matrix size.
