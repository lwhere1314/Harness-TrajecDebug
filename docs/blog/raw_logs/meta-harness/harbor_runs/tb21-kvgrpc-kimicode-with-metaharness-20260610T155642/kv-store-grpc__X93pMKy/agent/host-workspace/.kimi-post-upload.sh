#!/bin/bash
set -e

python3 -m pip install --break-system-packages grpcio==1.73.0 grpcio-tools==1.73.0

python3 -m grpc_tools.protoc -I/app --python_out=/app --grpc_python_out=/app /app/kv-store.proto

python3 - <<'PY'
import os
files = ["/app/kv_store_pb2.py", "/app/kv_store_pb2_grpc.py"]
header = '''import os
os.environ.setdefault("GRPC_ENABLE_HTTP_PROXY", "0")
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
'''
for path in files:
    with open(path, "r") as f:
        content = f.read()
    if not content.lstrip().startswith("import os"):
        with open(path, "w") as f:
            f.write(header + content)
PY

nohup python3 /app/server.py > /app/server.log 2>&1 &

sleep 2

python3 - <<'PY'
import os
os.environ["GRPC_ENABLE_HTTP_PROXY"] = "0"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

import grpc
from kv_store_pb2 import SetValRequest, GetValRequest
from kv_store_pb2_grpc import KVStoreStub

channel = grpc.insecure_channel("127.0.0.1:5328")
stub = KVStoreStub(channel)
resp = stub.SetVal(SetValRequest(key="__selftest_key", value=42))
assert resp.val == 42, f"Unexpected SetVal response: {resp}"
resp = stub.GetVal(GetValRequest(key="__selftest_key"))
assert resp.val == 42, f"Unexpected GetVal response: {resp}"
print("self-test passed")
PY
