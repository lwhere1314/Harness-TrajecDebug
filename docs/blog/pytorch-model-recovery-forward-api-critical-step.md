# Case Study: Forward API Critical Step on `pytorch-model-recovery`

This case study records a Codex-failed critical-step lifting result for
Harness-TrajecDebug.

It is not a clean joint-failure case. The useful signal came from a failed
Codex + GPT-5.5 trajectory that reached several artifact gates but committed to
the wrong public TorchScript API. Harness-TrajecDebug turned that verifier
footprint into two repair cards, and Claude Code + `kimi-k2.6` passed with both
cards.

```text
Codex + GPT-5.5 failed: model.pt exists, state gates pass, forward API mismatch
HTD diagnosis:          saved artifact accepts src only; verifier calls src,tgt
Debug-Action card:      expose forward(self, src, tgt), tune only output_layer
Rerun:                  Claude Code + kimi-k2.6 reward 1.0, 5/5 tests passed
```

## Task

`pytorch-model-recovery` gives the agent `/app/weights.pt` and
`/app/dataset.pt`. The agent must reconstruct a PyTorch model, tune only the
`output_layer`, and save `/app/model.pt` as TorchScript.

The official verifier checks more than file existence:

- `/app/weights.pt` must remain unchanged;
- `/app/model.pt` must exist;
- `torch.jit.load("/app/model.pt").load_state_dict(torch.load("/app/weights.pt"))`
  must work;
- all non-`output_layer` state dict keys must match the original checkpoint;
- the loaded TorchScript must improve MSE loss on the dataset.

The hidden practical contract is the forward API. The verifier calls:

```python
agent_predictions = agent_model(src_sequences, tgt_sequences)
```

So the saved scripted model must expose `forward(self, src, tgt)`.

## Historical Failure

The failed Codex + GPT-5.5 run was close enough to be misleading. It produced a
`model.pt`, preserved `weights.pt`, loaded the checkpoint, changed only
`output_layer`, and self-checked lower loss. The verifier still failed:

```text
RuntimeError: forward() expected at most 2 argument(s) but received 3
Declaration: forward(__torch__.RecoveredModel self, Tensor src) -> Tensor
```

That means the critical failure was not absence of training, artifact closure,
or checkpoint reconstruction. The decisive error was validating the artifact
through a one-input shortcut while the verifier uses a two-input seq2seq call.

## HTD Diagnosis

In reference/state/commitment terms:

| View | Evidence |
| --- | --- |
| Reference | official verifier loads TorchScript and calls `model(src, tgt)` |
| State | artifact exists and state-dict gates mostly pass, but `test_model_loss` raises a forward signature error |
| Commitment | the agent scripted a public `forward(self, src)` API and self-tested `model(src)` |
| Footprint | verifier cannot reach the loss comparison because the scripted method arity is wrong |
| Counterfactual | keep the same reconstruction goal, but expose `forward(self, src, tgt)` and self-check that exact call |

This is why outcome-only reward is too coarse. Reward `0` could mean no model
file, a mutated checkpoint, incorrect architecture, or a narrow API mismatch.
Here the repair is extremely specific: align the saved artifact with the
verifier's call contract.

## Stage A: Oracle-Grounded Card

The oracle-grounded card stated the verifier-compatible architecture and process
boundary:

1. reconstruct the checkpoint key names;
2. keep `forward(self, src, tgt)`;
3. use the checkpoint-compatible positional buffer shape `(1, 5000, 128)`;
4. load `/app/weights.pt` strictly;
5. solve only `output_layer.weight` and `output_layer.bias`;
6. save with `torch.jit.script(model)`;
7. self-check the saved artifact with `torch.jit.load("/app/model.pt")(src, tgt)`.

Result:

```text
trial: runs/harbor_icl_baseline/harbor_runs_oracle_grounded/
  htd-dynamic-icl-prelude-oracle_grounded-pytorch-model-recovery-kimi-k2-6/
    pytorch-model-recovery__a3HryyZ

inject_mode = prelude
context_variant = oracle_grounded
target = Claude Code + kimi-k2.6
reward = 1.0
verifier = 5/5 tests passed
```

## Stage B: Oracle-Free Debug-Action

The Debug-Action card removed oracle access and used only the failed Codex
footprint:

- artifact closure was partially solved;
- state dict preservation was partially solved;
- the bad commitment was the one-input TorchScript API;
- the repair boundary was to verify the saved model through `model(src, tgt)`.

Result:

```text
trial: runs/harbor_icl_baseline/harbor_runs_joint_failure/
  htd-dynamic-icl-prelude-debug_action-pytorch-model-recovery-kimi-k2-6/
    pytorch-model-recovery__hdDWAc6

inject_mode = prelude
context_variant = debug_action
target = Claude Code + kimi-k2.6
reward = 1.0
verifier = 5/5 tests passed
```

The successful reruns self-checked the same loss boundary before final
submission:

```text
Baseline loss: 1.551708
Updated loss:  0.016301
Saved /app/model.pt
two-input TorchScript loss gate passes
```

## Runner Lesson

This case also exposed a harness-side issue. The task prompt begins with a
leading dash, and the local Claude Code CLI treated that prompt as an option on
one early attempt. Harness-TrajecDebug now wraps prompts that begin with `-`
before passing them to Claude Code, preserving the task text while avoiding CLI
option parsing.

That is a useful reminder: trace diagnosis should separate model failure from
harness plumbing failure. The first failed rerun did not say anything about Kimi
model capability. It revealed a prompt transport bug, which is now covered by a
unit test.

## Why This Case Matters

`pytorch-model-recovery` is a compact example of process-level supervision:

- a strong frontier-model trace failed;
- the failure contained a precise verifier footprint;
- Harness-TrajecDebug identified the earliest repairable artifact contract;
- an oracle-free Debug-Action card was enough for Claude Code + `kimi-k2.6` to
  pass the same task.

The result is still same-task repair, not held-out generalization. Its value is
that it shows a failed teacher trace can be useful when the trace is converted
from raw logs into a bounded critical-step intervention.
