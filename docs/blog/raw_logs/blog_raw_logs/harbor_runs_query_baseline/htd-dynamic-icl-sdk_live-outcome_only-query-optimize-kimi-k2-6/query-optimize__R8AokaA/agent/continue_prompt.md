HARNESS-TRAJECDEBUG CONTROLLER INJECTION

The previous Claude Code turn was allowed to start without the teacher context.
The runtime controller is now injecting context because the first turn either
hit a trigger, timed out, or did not close the expected artifact.

Use the injected context now. If it contains a same-task Debug-Action card with
a matching artifact path, materialize that artifact first and run the cheapest
closure check available. Avoid web fetches, heavyweight dependency installs, or
full recomputation whose only purpose is to reproduce a verified teacher
artifact.

Task: query-optimize
Teacher outcome: reward=1.0
Verifier summary: tests=6, passed=6, failed=0
