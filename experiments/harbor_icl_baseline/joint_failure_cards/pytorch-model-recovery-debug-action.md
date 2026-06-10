# Harness-TrajecDebug Debug-Action Card: pytorch-model-recovery

## Source Signal

This card is synthesized from a failed Codex + GPT-5.5 trajectory and the
official verifier footprint. It is not a teacher-success replay.

The failed run reached partial artifact closure:

- `/app/model.pt` existed;
- `/app/weights.pt` was unchanged;
- the saved model could load `/app/weights.pt`;
- the state dict differed from `/app/weights.pt` only in `output_layer`;
- Codex self-reported lower loss after tuning.

But the official verifier failed at `test_model_loss` before comparing losses:

```text
RuntimeError: forward() expected at most 2 argument(s) but received 3
Declaration: forward(__torch__.RecoveredModel self, Tensor src) -> Tensor
```

The failure was not "no model" or "no tuning." The critical error was an API
contract mismatch: the saved TorchScript model exposed `forward(self, src)`,
while the verifier calls `agent_model(src_sequences, tgt_sequences)`.

## Critical Step

The decisive action is to make artifact verification use the official API:

> Save a TorchScript `RecoveredModel` whose `forward(self, src, tgt)` exactly
> matches the verifier's two-input call, and compute both baseline and tuned
> loss through that same two-input forward.

Do not validate with a one-input helper such as `model(src)`.

## Action Boundary

Build `/app/model.pt` around these constraints:

1. Define the recovered module hierarchy with the original checkpoint key names:
   `embedding`, `pos_encoder`, `transformer_encoder`, `transformer_decoder`,
   and `output_layer`.
2. Use the verifier-compatible Transformer settings:
   `input_dim=64`, `d_model=128`, `nhead=4`, `num_encoder_layers=3`,
   `num_decoder_layers=1`, `dim_feedforward=256`, `dropout=0.0`.
3. Keep `forward(self, src, tgt)`, not `forward(self, src)`.
4. Preserve checkpoint shape compatibility. In particular, `pos_encoder.pe` in
   `/app/weights.pt` has shape `(1, 5000, 128)`, so use `pe.unsqueeze(0)`, not
   `pe.unsqueeze(0).transpose(0, 1)`.
5. Use `batch_first=True` and keep `src_sequences` / `tgt_sequences` in their
   native `(batch, seq, feature)` layout. Do not add manual transposes unless
   the strict checkpoint load and self-check prove they are correct.
6. Load `/app/weights.pt` strictly before tuning.
7. Freeze every non-output parameter. Only `output_layer.weight` and/or
   `output_layer.bias` may change.
8. Tune the last layer using the same `(src_sequences, tgt_sequences)` call path
   that the verifier will use.
9. Save `/app/model.pt` with `torch.jit.script(model)`.

## Minimal Coding Plan

Use a pre-output feature helper internally, but keep the public forward
two-input:

```python
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # shape (1, 5000, 128)

    def forward(self, x):
        return x + self.pe[:, : x.size(1)]

class RecoveredModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.embedding = nn.Linear(64, 128)
        self.pos_encoder = PositionalEncoding(128)
        enc = nn.TransformerEncoderLayer(
            d_model=128, nhead=4, dim_feedforward=256, dropout=0.0, batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(enc, num_layers=3)
        dec = nn.TransformerDecoderLayer(
            d_model=128, nhead=4, dim_feedforward=256, dropout=0.0, batch_first=True
        )
        self.transformer_decoder = nn.TransformerDecoder(dec, num_layers=1)
        self.output_layer = nn.Linear(128, 64)

def decode_features(self, src, tgt):
    src = self.pos_encoder(self.embedding(src))
    tgt = self.pos_encoder(self.embedding(tgt))
    memory = self.transformer_encoder(src)
    return self.transformer_decoder(tgt, memory)

def forward(self, src, tgt):
    return self.output_layer(self.decode_features(src, tgt))
```

A robust repair is to solve the output layer by least squares:

```python
weights = torch.load('/app/weights.pt', map_location='cpu')
dataset = torch.load('/app/dataset.pt', map_location='cpu')
src = dataset['src_sequences']
tgt = dataset['tgt_sequences']

model.load_state_dict(weights, strict=True)
model.eval()
with torch.no_grad():
    original_loss = torch.nn.functional.mse_loss(model(src, tgt), tgt)
    features = model.decode_features(src, tgt).reshape(-1, 128)
    target = tgt.reshape(-1, 64)
    design = torch.cat([features, torch.ones(features.shape[0], 1)], dim=1)
    solution = torch.linalg.lstsq(design, target).solution
    model.output_layer.weight.copy_(solution[:-1].T.contiguous())
    model.output_layer.bias.copy_(solution[-1].contiguous())
    updated_loss = torch.nn.functional.mse_loss(model(src, tgt), tgt)
```

Then assert `updated_loss < original_loss` and that every changed state key
contains `output_layer`.

## Avoided Failure Patterns

Do not:

- script a model whose public `forward` takes only `src`;
- self-check with `model(src)` when the verifier uses `model(src, tgt)`;
- register `pos_encoder.pe` with shape `(5000, 1, 128)` when the checkpoint has
  `(1, 5000, 128)`;
- transpose the dataset tensors unless the checkpoint strict-load and
  two-input self-check both pass;
- change `embedding`, positional encoding, encoder, or decoder parameters;
- mutate `/app/weights.pt`;
- stop after `load_state_dict` succeeds, because checkpoint compatibility does
  not prove the forward API or loss gate.

## Self-Check

Run this after saving `/app/model.pt`:

```bash
python - <<'PY'
import torch
weights = torch.load('/app/weights.pt', map_location='cpu')
dataset = torch.load('/app/dataset.pt', map_location='cpu')
src = dataset['src_sequences']
tgt = dataset['tgt_sequences']

updated = torch.jit.load('/app/model.pt', map_location='cpu')
baseline = torch.jit.load('/app/model.pt', map_location='cpu')
baseline.load_state_dict(weights, strict=True)

updated.eval()
baseline.eval()
with torch.no_grad():
    base_loss = torch.nn.functional.mse_loss(baseline(src, tgt), tgt)
    new_loss = torch.nn.functional.mse_loss(updated(src, tgt), tgt)

changed = [
    key for key, value in updated.state_dict().items()
    if not torch.equal(value, weights[key])
]
assert new_loss < base_loss, (float(new_loss), float(base_loss))
assert changed and all('output_layer' in key for key in changed), changed
print('two-input TorchScript loss gate passes')
PY
```

If this exact check passes, the historical Codex failure mode has been repaired:
artifact closure, state-dict compatibility, and forward API compatibility are
all aligned.
