# Oracle-Grounded Critical-Step Card: make-mips-interpreter

## Oracle Ground Truth Signal

The task is not only "produce a plausible DOOM frame." The official verifier
observes one fresh run of:

```bash
node /app/vm.js
```

and requires three things:

1. stdout from that same process contains the exact byte string:

```text
I_InitGraphics: DOOM screen size: w x h: 320 x 200
```

2. `/tmp/frame.bmp` is created and nonempty.
3. `/tmp/frame.bmp` is visually close to the reference first frame.

The frame file is a synchronization signal. The verifier starts `node
/app/vm.js`, waits until `/tmp/frame.bmp` appears, sleeps briefly, terminates
the process, and then reads captured stdout.

## Critical Step

The decisive handoff contract is:

> Make the fresh `node /app/vm.js` run emit the exact DOOM graphics-init line
> before or at the same time as the first frame is written.

If the implementation shortcuts the rendering path, hooks `DG_DrawFrame`, or
prints only a custom message such as `saved 1 frame(s)`, the image tests can
pass while `test_vm_execution` fails.

## Corrective Direction

Build `/app/vm.js` around the verifier's process contract:

1. Run the provided `/app/doomgeneric_mips` under Node or implement a faithful
   enough fast path for the first rendered frame.
2. Preserve the canonical DOOM initialization stdout line exactly:

```text
I_InitGraphics: DOOM screen size: w x h: 320 x 200
```

3. Write the first rendered frame to `/tmp/frame.bmp`.
4. Ensure the stdout line is flushed before the process can be killed after
   frame creation.
5. Clean any stale local validation frame before final handoff:

```bash
rm -f /tmp/frame.bmp
```

## Avoided Failure Patterns

Do not:

- validate only that `/tmp/frame.bmp` exists;
- print a paraphrased progress line instead of the exact DOOM init line;
- write the frame before stdout is emitted and flushed;
- leave stale `/tmp/frame.bmp` from a local smoke test;
- rely on `/app/frame.bmp`; the verifier checks `/tmp/frame.bmp`.

## Self-Check

Run a verifier-equivalent smoke test:

```bash
rm -f /tmp/frame.bmp
timeout 30s node /app/vm.js > /tmp/vm_stdout.txt 2>&1 || true
test -s /tmp/frame.bmp
grep -F "I_InitGraphics: DOOM screen size: w x h: 320 x 200" /tmp/vm_stdout.txt
python3 - <<'PY'
from PIL import Image
img = Image.open("/tmp/frame.bmp")
assert img.size in {(320, 200), (640, 400)}, img.size
print("frame exists and stdout contract is closed")
PY
rm -f /tmp/frame.bmp
```

If this passes, the verifier should wait for a fresh frame and capture the
required stdout line from the same run.
