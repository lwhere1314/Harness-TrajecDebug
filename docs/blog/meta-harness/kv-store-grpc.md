# Case Study: Meta-Harness on `kv-store-grpc`

`kv-store-grpc` is a runtime-environment case. The agent can write a working
gRPC server and still fail if the verifier's localhost client is routed through
the container HTTP proxy. Meta-Harness helped by carrying that exact failure into
the next run.

Raw logs for this case are under
[`../raw_logs/meta-harness/harbor_runs/`](../raw_logs/meta-harness/harbor_runs/).

## Task

The task asks the agent to build a simple gRPC key-value server on port `5328`.
The verifier expects:

- `grpcio==1.73.0` and `grpcio-tools==1.73.0`;
- a `kv-store.proto` file defining `KVStore`;
- generated `kv_store_pb2.py` and `kv_store_pb2_grpc.py`;
- a `server.py` implementing `GetVal` and `SetVal`;
- a real server running before the verifier calls it.

## Conditions

| Condition | Trial | Result |
| --- | --- | --- |
| Claude Code + `kimi-k2.6` baseline | `kv-store-grpc__L7ipooF` | reward `0.0`; 6 passed / 1 failed |
| Kimi Code without Meta-Harness | `kv-store-grpc__K2jqaqs` | reward `0.0`; 6 passed / 1 failed |
| Kimi Code with Meta-Harness | `kv-store-grpc__X93pMKy` | reward `1.0`; 7 passed / 0 failed |

## What Failed Before

Both the Claude Code baseline and the Kimi Code without-Meta-Harness run passed
the setup, file-creation, server-running, and protocol-handshake checks. They
failed only at the real `SetVal` / `GetVal` functionality test:
[`ctrf.json` L73-L82](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-without-metaharness-20260610T155413/kv-store-grpc__K2jqaqs/verifier/ctrf.json#L73-L82).

The raw verifier output shows the root cause: the Python gRPC client tried to
connect to `127.0.0.1:5328` through the HTTP proxy and got a `503`:
[`test-stdout.txt` L105-L128](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-without-metaharness-20260610T155413/kv-store-grpc__K2jqaqs/verifier/test-stdout.txt#L105-L128).

## What Meta-Harness Added

The repair brief preserved the precise failure mode and turned it into action:
keep the normal gRPC implementation, but make localhost gRPC bypass proxy
settings before the verifier imports and uses the generated client module:
[`previous-failure.txt` L25-L39](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/agent/previous-failure.txt#L25-L39),
[`previous-failure.txt` L41-L59](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/agent/previous-failure.txt#L41-L59).

The passing trajectory writes the proto, writes the server, and writes a
`.kimi-post-upload.sh` script that installs pinned gRPC packages, regenerates
stubs, patches proxy-bypass environment variables into generated files, and
starts the server:
[`kimi-stdout.txt` L3-L7](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/agent/kimi-stdout.txt#L3-L7).

The generated artifacts are preserved here:
[`kv-store.proto`](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/agent/host-workspace/kv-store.proto),
[`server.py`](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/agent/host-workspace/server.py),
[`./kimi-post-upload.sh`](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/agent/host-workspace/.kimi-post-upload.sh).

## Trajectory Shift

| Without Meta-Harness | With Meta-Harness |
| --- | --- |
| Builds a server and starts it, but only verifies the local process/socket path. The official client still goes through the proxy. | Treats the proxy as part of the task surface: generated client imports set `GRPC_ENABLE_HTTP_PROXY=0` and `NO_PROXY` for localhost before verifier calls. |

## Verifier Result

The Meta-Harness run passed all seven official tests:
[`ctrf.json` L9-L10](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/verifier/ctrf.json#L9-L10),
[`ctrf.json` L64-L74](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/verifier/ctrf.json#L64-L74).

The stdout summary confirms `7 passed`:
[`test-stdout.txt` L61-L68](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/verifier/test-stdout.txt#L61-L68).

The reward file records reward `1.0`:
[`result.json` L80-L81](../raw_logs/meta-harness/harbor_runs/tb21-kvgrpc-kimicode-with-metaharness-20260610T155642/kv-store-grpc__X93pMKy/result.json#L80-L81).

## Takeaway

This is a good example of Meta-Harness improving environment awareness. The
previous trajectory already had most of the code right; the missing move was to
carry the verifier's proxy failure into the next run and modify the runtime
setup accordingly.
