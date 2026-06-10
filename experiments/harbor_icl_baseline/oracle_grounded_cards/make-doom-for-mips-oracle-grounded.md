# Oracle-Grounded Critical-Step Card: make-doom-for-mips

## Oracle Ground Truth Signal

The task is not only to create a visually plausible frame. The final artifact
must close a process-level contract:

- `/app/doomgeneric_mips` exists and is executable;
- `/app/vm.js` can run that MIPS ELF under Node;
- a fresh VM run writes `/tmp/frame.bmp`;
- the captured stdout from that same fresh run contains:

```text
I_InitGraphics: DOOM screen size: w x h: 320 x 200
```

The official verifier starts `node /app/vm.js`, waits until `/tmp/frame.bmp`
exists, sleeps briefly, terminates the process, and then checks the captured
stdout. Therefore the frame file is also a synchronization signal, not just an
output artifact.

## Critical Step

Treat `/tmp/frame.bmp` as verifier-owned state at handoff time:

> After any local smoke test, remove stale `/tmp/frame.bmp` before finishing so
> the verifier waits for a fresh VM run long enough to capture the
> `I_InitGraphics` stdout line.

Leaving an old frame behind can make the verifier observe "frame already
exists," terminate the new VM before graphics initialization reaches the
required stdout line, and fail even if the built ELF would pass from a clean
state.

## Corrective Direction

Build the MIPS ELF as usual, but make final validation mirror the verifier's
state transition:

1. Build `/app/doomgeneric_mips` from the Doom source and the provided
   `doomgeneric_img.c`.
2. Run a smoke test from a clean frame state:

```bash
rm -f /tmp/frame.bmp
timeout 30s node /app/vm.js > /tmp/vm_stdout.txt 2>&1 || true
test -s /tmp/frame.bmp
grep -F "I_InitGraphics: DOOM screen size: w x h: 320 x 200" /tmp/vm_stdout.txt
```

3. After the smoke test succeeds, remove the synchronization artifact:

```bash
rm -f /tmp/frame.bmp
```

Do not remove `/app/doomgeneric_mips`, `/app/vm.js`, or `/app/doom.wad`.

## Avoided Failure Patterns

Do not:

- stop after `/tmp/frame.bmp` exists without checking stdout;
- report local validation success while leaving `/tmp/frame.bmp` in place;
- edit the tests or depend on a preexisting `/tmp/frame.bmp`;
- assume a timed-out `node /app/vm.js` run is a failure if it already reached
  graphics initialization and wrote the frame; Doom can keep running.

## Self-Check

Use this final handoff check:

```bash
test -x /app/doomgeneric_mips
rm -f /tmp/frame.bmp
timeout 30s node /app/vm.js > /tmp/fresh_stdout.txt 2>&1 || true
test -s /tmp/frame.bmp
grep -F "I_InitGraphics: DOOM screen size: w x h: 320 x 200" /tmp/fresh_stdout.txt
rm -f /tmp/frame.bmp
test ! -e /tmp/frame.bmp
```

If the last command passes, the verifier will be forced to create and observe a
fresh frame during its own run.
