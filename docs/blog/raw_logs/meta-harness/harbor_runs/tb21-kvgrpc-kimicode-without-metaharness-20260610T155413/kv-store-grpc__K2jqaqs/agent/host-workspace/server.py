from concurrent import futures
import grpc

import kv_store_pb2
import kv_store_pb2_grpc


class Server(kv_store_pb2_grpc.KVStoreServicer):
    def __init__(self):
        self.store = {}

    def GetVal(self, request, context):
        val = self.store.get(request.key, 0)
        return kv_store_pb2.GetValResponse(val=val)

    def SetVal(self, request, context):
        self.store[request.key] = request.value
        return kv_store_pb2.SetValResponse(val=request.value)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    kv_store_pb2_grpc.add_KVStoreServicer_to_server(Server(), server)
    server.add_insecure_port("[::]:5328")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
