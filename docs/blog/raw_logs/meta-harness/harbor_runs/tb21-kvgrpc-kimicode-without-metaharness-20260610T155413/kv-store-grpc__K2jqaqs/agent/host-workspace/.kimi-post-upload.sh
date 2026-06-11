#!/bin/bash
set -e

# Install grpcio and grpcio-tools system-wide
pip install grpcio==1.73.0 grpcio-tools==1.73.0

# Generate Python gRPC code from the proto file
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. kv-store.proto

# Run the server in the background
python server.py &
