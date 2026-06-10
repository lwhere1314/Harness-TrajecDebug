# Oracle-Grounded Critical-Step Card: pytorch-model-recovery

## Oracle Ground Truth Signal

The oracle-level signal is not just "make a TorchScript file." It is:

- reconstruct the verifier-compatible Transformer module hierarchy from
  `/app/weights.pt`;
- preserve the public forward API expected by the verifier:
  `forward(self, src, tgt)`;
- load the original checkpoint strictly;
- update only `output_layer` parameters;
- save `/app/model.pt` as TorchScript;
- verify the saved TorchScript with the same two-input call used by the
  official test.

So the critical step is an artifact API decision:

> The saved TorchScript model must accept `(src_sequences, tgt_sequences)`, not
> a custom one-input shortcut.

## Corrective Direction

Use the architecture implied by the verifier and checkpoint names:

```python
self.embedding = nn.Linear(64, 128)
self.pos_encoder = PositionalEncoding(128)
self.transformer_encoder = nn.TransformerEncoder(..., num_layers=3)
self.transformer_decoder = nn.TransformerDecoder(..., num_layers=1)
self.output_layer = nn.Linear(128, 64)
```

Use `nhead=4`, `dim_feedforward=256`, and `dropout=0.0`. The checkpoint stores
`pos_encoder.pe` with shape `(1, 5000, 128)`, so the positional buffer should be
created with `pe.unsqueeze(0)`, not transposed to `(5000, 1, 128)`. A robust
implementation can use `batch_first=True` and keep the dataset tensors in their
native `(batch, seq, feature)` layout. The verifier calls:

```python
agent_model = torch.jit.load("/app/model.pt")
agent_predictions = agent_model(src_sequences, tgt_sequences)
```

Therefore the class should expose:

```python
def forward(self, src, tgt):
    src = self.embedding(src)
    src = self.pos_encoder(src)
    tgt = self.embedding(tgt)
    tgt = self.pos_encoder(tgt)
    memory = self.transformer_encoder(src, None)
    output = self.transformer_decoder(tgt, memory, None, None)
    return self.output_layer(output)
```

Do not save a model whose `forward` accepts only `src`.

## Minimal Coding Plan

Fit the last layer in closed form instead of relying on a short training loop.
Add a helper that returns the decoder features before `output_layer`, then solve
a linear least-squares problem for `output_layer.weight` and
`output_layer.bias`.

```python
import math
import torch
import torch.nn as nn

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
        self.register_buffer("pe", pe.unsqueeze(0))

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

weights = torch.load("/app/weights.pt", map_location="cpu")
dataset = torch.load("/app/dataset.pt", map_location="cpu")
src = dataset["src_sequences"]
tgt = dataset["tgt_sequences"]

model = RecoveredModel()
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

assert updated_loss < original_loss, (updated_loss, original_loss)
changed = [
    key for key, value in model.state_dict().items()
    if not torch.equal(value, weights[key])
]
assert all("output_layer" in key for key in changed), changed

model.eval()
scripted = torch.jit.script(model)
scripted.save("/app/model.pt")
```

## Critical Verifier Gates

Before finishing, test the saved artifact exactly like the verifier:

```bash
python - <<'PY'
import torch
weights = torch.load('/app/weights.pt', map_location='cpu')
dataset = torch.load('/app/dataset.pt', map_location='cpu')
src, tgt = dataset['src_sequences'], dataset['tgt_sequences']

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
print('verifier-compatible TorchScript passes local loss and state checks')
PY
```

The important check is not only that the file exists. It must load, accept two
inputs, load the original checkpoint strictly, and improve loss with only
`output_layer` changed.
