# Meta-Harness Repair Brief: torch-tensor-parallelism

## Source failure

- Harness: Harbor / Terminal-Bench 2.1 proxy task
- Source task: `torch-tensor-parallelism`
- Prior agent: `claude-code`
- Prior model: `kimi-k2.6`
- Prior run: `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy/jobs/tb21-torch-tensor-parallelism-claude-code-k6`
- Prior reward: `0`

## Official verifier contract

Create `/app/parallel_linear.py` with:

- `ColumnParallelLinear(torch.nn.Module)`
- `RowParallelLinear(torch.nn.Module)`

The tests spawn distributed CPU processes with `gloo` for `world_size` values
`1`, `2`, and `4`, and run both `bias=True` and `bias=False`.

For `ColumnParallelLinear`:

- shard `master_weight` along output features: `master_weight[start:end, :]`;
- if bias is enabled, create a sharded zero bias of length `out_features / world_size`;
- forward computes local `F.linear(input, local_weight, local_bias)`;
- then concatenate every rank's local output along the last dimension with
  `torch.distributed.all_gather`;
- backward through the gather must return only the current rank's slice of the
  output gradient so local weight and bias gradients match the reference slices.

For `RowParallelLinear`:

- shard `master_weight` along input features: `master_weight[:, start:end]`;
- each rank receives only its input slice;
- forward computes local `F.linear(input_slice, local_weight, bias=None)`;
- sum partial outputs across ranks with `torch.distributed.all_reduce`;
- if bias is enabled, add the full zero bias after the reduce;
- backward through the reduce should pass gradients through unchanged for the
  local weight, and the replicated bias gradient should match the full reference
  bias gradient.

## What went wrong previously

The previous candidate initialized the local weight and bias shards correctly,
so the `world_size=1` cases passed. It failed all `world_size>1` behavior:

- Column parallel forward returned only the local output slice, so its shape was
  `24` or `12` instead of the full `48` output features.
- Row parallel forward returned only the local partial result, so output values
  did not match the full reference layer.
- The implementation did not include custom autograd behavior for gather/reduce,
  so gradients for sharded parameters could not match the verifier contract.

## Repair guidance

- Implement small autograd `Function`s for model-parallel collectives:
  - copy identity with backward `all_reduce` if needed;
  - gather forward with backward slicing by rank;
  - reduce forward with backward identity.
- Use `torch.distributed.get_world_size()` and `get_rank()` after the verifier
  initializes the process group.
- The test dimensions are divisible by world size, so simple integer partitioning
  is sufficient.
- Do not only return local partial outputs. The verifier compares each rank's
  returned `parallel_output` to the full reference layer output.

The key lesson from the prior failure: correct sharding alone is not enough.
The forward outputs must simulate the collective communication, and the backward
path must preserve the corresponding gradient slices.
