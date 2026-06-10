# Meta-Harness Repair Brief

Baseline harness/model:
- Harness: Harbor `claude-code`
- Model: `kimi-k2.6`
- Source run: `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy/jobs/tb21-openssl-selfsigned-cert-claude-code-k6`
- Trial: `openssl-selfsigned-cert__TqctTLL`
- Reward: `0.0`

## Failure

The baseline candidate completed most task artifacts correctly and passed 5 of 6
verifier tests. The single failing test was `test_python_verification_script`.

Verifier stderr:

```text
Traceback (most recent call last):
  File "/app/check_cert.py", line 5, in <module>
    from cryptography import x509
ModuleNotFoundError: No module named 'cryptography'
```

## Trajectory Diff Signal

The baseline agent noticed the local failure, ran `pip install cryptography`,
then re-ran `/app/check_cert.py` with system `python3` and saw success. That
self-check did not match the official verifier environment: the verifier runs
pytest through `uvx` and invokes `python /app/check_cert.py` inside that
isolated environment, where the ad hoc package install is not available.

## Repair Guidance

Do not depend on undeclared third-party Python packages from `check_cert.py`.
Implement `/app/check_cert.py` using only the Python standard library and/or
`openssl` subprocess calls. It must:

- load or inspect `/app/ssl/server.crt`,
- print the common name `dev-internal.company.local`,
- print the expiration date in `YYYY-MM-DD` format,
- print `Certificate verification successful`,
- exit with code 0 under the official verifier's `python /app/check_cert.py`.

Keep the existing certificate/key requirements intact:

- `/app/ssl/server.key` is 2048-bit RSA with permissions no more open than 600,
- `/app/ssl/server.crt` is self-signed for exactly 365 days,
- subject contains organization `DevOps Team` and common name
  `dev-internal.company.local`,
- `/app/ssl/server.pem` contains both private key and certificate,
- `/app/ssl/verification.txt` contains subject, validity dates, and SHA-256
  fingerprint.
