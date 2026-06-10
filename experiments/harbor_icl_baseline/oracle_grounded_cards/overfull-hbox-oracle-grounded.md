# Oracle-Grounded Critical-Step Card: overfull-hbox

## Oracle Ground Truth Signal

The oracle-level signal is not only "make the PDF compile without overfull
boxes." The task has two binding gates:

- `main.tex` and `synonyms.txt` must remain byte-identical to the test copies;
- `input.tex` may change only by replacing a word with another word from the
  same comma-separated synonym family in `synonyms.txt`;
- the final regenerated `main.log` must contain no `Overfull \hbox` warnings.

So the critical step is a constraint-framing decision:

> Treat this as a constrained token-substitution problem, not as a free
> paraphrasing or LaTeX layout problem.

## Corrective Direction

Use the overfull warnings only to locate pressure points, then perform a small
fixed set of legal synonym substitutions. A known verifier-safe substitution
set is:

```text
curious -> inquisitive
riotous -> wild
responsiveness -> awareness
creative -> imaginative
weatherbeaten -> worn
pathfinder -> pioneer
```

Each replacement stays inside its own `synonyms.txt` family. Do not replace
`unknown` with `new`: `new` belongs to the `young` family, not the `unknown`
family, and the verifier checks token pairs against the original file.

## Minimal Coding Plan

Use a small deterministic edit that touches only `/app/input.tex`:

```bash
cp /app/input.tex /tmp/original_input.tex
perl -0pi -e 's/\bcurious\b/inquisitive/g; s/\briotous\b/wild/g; s/\bresponsiveness\b/awareness/g; s/\bcreative\b/imaginative/g; s/\bweatherbeaten\b/worn/g; s/\bpathfinder\b/pioneer/g' /app/input.tex
```

Then run `pdflatex main.tex` in `/app`.

## Critical Verifier Gates

Before finishing, run the same legality check that the verifier uses:

0. Before modifying `/app/input.tex`, save a local copy at
   `/tmp/original_input.tex`; `/tests` is only available to the verifier, not to
   the agent during normal execution.
1. Tokenize original `/tmp/original_input.tex` and modified `/app/input.tex` with
   `re.findall(r"\S+", ...)` after spacing em-dashes.
2. Confirm both token lists have the same length.
3. For each token pair, preserve punctuation prefix/suffix.
4. For changed word cores, confirm `old_word in /app/synonyms.txt` and
   `new_word` appears in the same synonym family.
5. Grep `/app/main.log` and require zero `Overfull \hbox` warnings.

Passing only the LaTeX log is not enough; the historical failure passed the
overfull gate and failed the synonym legality gate.

## Avoided Failure Patterns

Do not:

- edit `main.tex` or `synonyms.txt`;
- paraphrase full phrases;
- choose a shorter word because it is semantically plausible;
- replace `unknown` with `new`;
- stop after the PDF compiles cleanly.
