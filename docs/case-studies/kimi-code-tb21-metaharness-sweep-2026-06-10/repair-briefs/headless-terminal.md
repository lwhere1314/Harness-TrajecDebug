# headless-terminal prior failure brief

Prior failure source: `claude-code + kimi-k2.6` in
`tb21-kimi-k26-local-019e737a-colima16g-proxy`, task
`headless-terminal`.

Observed verifier result: 6 tests passed and
`test_background_commands` failed. The test starts
`python -m http.server 8000 --directory /server &` through
`HeadlessTerminal`, waits 5 seconds, then calls
`requests.get("http://localhost:8000")`. The response status was `503`
instead of `200`.

Prior candidate shape:

- Implemented `/app/headless_terminal.py` with `pexpect.spawn("bash", ["-i"])`.
- Supported normal commands, Vim interaction, Ctrl-C, startup files, and shell
  state persistence.
- Did not account for proxy environment affecting localhost HTTP checks.

Repair guidance:

- Keep a real interactive bash process attached to a pty.
- If using `pexpect`, install it in the task container via
  `.kimi-post-upload.sh`; host-only installs will not affect verification.
- Ensure localhost traffic bypasses any configured proxy for both the verifier
  Python process and the spawned shell. In particular, set or preserve
  `NO_PROXY`/`no_proxy` entries for `localhost`, `127.0.0.1`, and `::1`.
- Avoid solutions that execute each command in a fresh subprocess, because the
  tests require shell state and background jobs to persist across calls.
