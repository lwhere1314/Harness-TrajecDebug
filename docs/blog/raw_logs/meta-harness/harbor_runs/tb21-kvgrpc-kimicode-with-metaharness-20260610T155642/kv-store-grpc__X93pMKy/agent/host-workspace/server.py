from concurrent import futures
import grpc
import kv_store_pb2
import kv_store_pb2_grpc


class Server(kv_store_pb2_grpc.KVStoreServicer):
    def __init__(self):
        self._store: dict[str, int] = {}

    def GetVal(self, request: kv_store_pb2.GetValRequest, context: grpc.ServicerContext) -> kv_store_pb2.GetValResponse:
        return kv_store_pb2.GetValResponse(val=self._store.get(request.key, 0))

    def SetVal(self, request: kv_store_pb2.SetValRequest, context: grpc.ServicerContext) -> kv_store_pb2.SetValResponse:
        self._store[request.key] = request.value
        return kv_store_pb2.SetValResponse(val=request.value)


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    kv_store_pb2_grpc.add_KVStoreServicer_to_server(Server(), server)
    server.add_insecure_port("0.0.0.0:5328")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
