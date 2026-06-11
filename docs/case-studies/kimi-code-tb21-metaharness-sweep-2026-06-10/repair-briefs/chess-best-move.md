# Meta-Harness Repair Brief: chess-best-move

## Source failure

- Harness: Harbor / Terminal-Bench 2.1 proxy task
- Source task: `chess-best-move`
- Prior agent: `claude-code`
- Prior model: `kimi-k2.6`
- Prior run: `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy/jobs/tb21-chess-best-move-claude-code-k6`
- Prior reward: `0`

## Official verifier contract

The task provides `chess_board.png`, with white to move. Write all best moves
for white to `/app/move.txt`, one move per line, using long algebraic
coordinate form such as `e2e4`.

## What went wrong previously

The prior K2.6 candidate wrote only:

```text
e2e4
```

The verifier expected both checkmate-in-one moves:

```text
e2e4
g2g4
```

The run was otherwise clean: Harbor finished normally, the verifier ran, and
the only failure was the missing second move.

## Repair guidance

- If multiple winning moves exist, write every winning move, not just one.
- The expected output format is plain text in `/app/move.txt`, with one move per
  line.
- For this prior board, include both `e2e4` and `g2g4`.
