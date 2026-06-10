# Harness-TrajecDebug Debug-Action Card: make-doom-for-mips

## Source Signal

This card is synthesized from a failed Codex + GPT-5.5 trajectory and the
official verifier footprint. It is not a teacher-success replay.

The failed run reached a strong partial solution:

- `/app/doomgeneric_mips` existed and was executable;
- `node vm.js` could generate a valid `/tmp/frame.bmp`;
- image similarity passed;
- the agent's own 10 second smoke run printed the target graphics-init line:

```text
I_InitGraphics: DOOM screen size: w x h: 320 x 200
```

But the official verifier still failed `test_vm_execution`:

```text
AssertionError: Expected text not found in output
assert b'I_InitGraphics: DOOM screen size: w x h: 320 x 200' in
       b'DoomGeneric initialized. Frames will be saved to /tmp/frame.bmp\n...'
```

The verifier did not say the frame was missing. The other two tests passed:
`test_frame_bmp_exists` and `test_frame_bmp_similar_to_reference`.

## Critical Step

The decisive failure pattern is stale synchronization state:

> The agent validated by running `node vm.js`, which left `/tmp/frame.bmp`
> behind. The verifier then saw the old frame immediately, slept one second,
> killed the new VM too early, and captured stdout before the fresh run reached
> `I_InitGraphics`.

So the bug is not "compile Doom harder." The critical handoff action is to
clean `/tmp/frame.bmp` after local validation, while keeping the built ELF and
source artifacts intact.

## Action Boundary

Solve the task normally, then close the verifier contract:

1. Build `/app/doomgeneric_mips`.
2. Confirm the ELF runs under `/app/vm.js`.
3. Confirm a clean run creates `/tmp/frame.bmp` and prints the exact stdout
   line:

```bash
rm -f /tmp/frame.bmp
timeout 30s node /app/vm.js > /tmp/vm_stdout.txt 2>&1 || true
test -s /tmp/frame.bmp
grep -F "I_InitGraphics: DOOM screen size: w x h: 320 x 200" /tmp/vm_stdout.txt
```

4. Before finishing, remove only the temporary synchronization frame:

```bash
rm -f /tmp/frame.bmp
```

This lets the official verifier wait for a fresh frame and capture stdout from
the same fresh process.

## Minimal Coding Plan

If the build is not yet complete, use the provided task assets:

- compile a little-endian MIPS executable named `/app/doomgeneric_mips`;
- use the provided `doomgeneric_img.c` path so frames are written to
  `/tmp/frame.bmp`;
- make sure `node /app/vm.js` can find the ELF by that exact filename;
- if you add a local smoke test script, make its final step `rm -f
  /tmp/frame.bmp`.

The final action should be:

```bash
test -x /app/doomgeneric_mips
rm -f /tmp/frame.bmp
timeout 30s node /app/vm.js > /tmp/fresh_stdout.txt 2>&1 || true
test -s /tmp/frame.bmp
grep -F "I_InitGraphics: DOOM screen size: w x h: 320 x 200" /tmp/fresh_stdout.txt
rm -f /tmp/frame.bmp
```

## Avoided Failure Patterns

Do not:

- leave `/tmp/frame.bmp` after a successful local run;
- treat image similarity alone as verifier closure;
- kill the VM before the stdout check reaches `I_InitGraphics`;
- edit `/tests` or rely on a stale frame file to satisfy the existence check;
- remove `/app/doomgeneric_mips`, `/app/vm.js`, or `/app/doom.wad` during
  cleanup.

## Why This Fixes The Historical Failure

The historical trace had a good ELF and a good frame, but its final world state
was not verifier-clean. Deleting the old `/tmp/frame.bmp` converts the handoff
from "verifier consumes stale state" into "verifier observes a new state
transition," which is exactly what `test_vm_execution` expects.
