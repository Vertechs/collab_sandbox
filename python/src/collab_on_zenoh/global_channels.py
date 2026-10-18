import zenoh
import queue
import uuid
import struct

from dataclasses import dataclass
from collections.abc import Callable


GLOBAL_REQUESTS_KEY = "@zvez/global/requests"
GLOBAL_RESPONSES_KEY = "@zvez/global/responses"
GLOBAL_PRODUCERS_KEY = "@zvez/global/producers"
GLOBAL_CONSUMERS_KEY = "@zvez/global/consumers"


@dataclass #TODO implement as class
class ZvezRequestLink:
    def __init__(self, web_id: uuid.UUID, edge_id: int, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr):
        self.web_id = web_id
        self.edge_id = edge_id
        self.consumer_key = consumer_key
        self.producer_key = producer_key


class ZvezNodeGlobalChannels:
    def __init__(self,session: zenoh.Session, request_callback: Callable[[dict], None] | None = None):
        self.requests_queue = queue.Queue()
        self.responses_queue = queue.Queue()

        self.request_callback = request_callback

        self._requests_subscriber = session.declare_subscriber(GLOBAL_REQUESTS_KEY, self._request_handler)

        self._responses_publisher = session.declare_publisher(GLOBAL_RESPONSES_KEY)
        self._producers_publisher = session.declare_publisher(GLOBAL_PRODUCERS_KEY)
        self._consumers_publisher = session.declare_publisher(GLOBAL_CONSUMERS_KEY)


    def _request_handler(self, sample):
        msg_str = sample.payload.decode()
        msg_type = msg_str[0:msg_str.index("\x00")]
        msg_data = msg_str[msg_str.index("\x00")+1:]

        #TODO add checks for valid format, break into functions
        if msg_type == b"LINK":
            e1 = msg_data.index("\x00")
            request = {
                "type": 'link',
                "webID": uuid.UUID(bytes=struct.unpack("16s", msg_data[0:16])[0]),
                "edgeID": struct.unpack("<L", msg_data[16:20])[0],
                "consumer_key": zenoh.KeyExpr(msg_data[20:e1]),
                "producer_key": zenoh.KeyExpr(msg_data[e1+1:]),
            }
        elif sample.payload[0:4] == b"ECHO":
            request = {
                "type": 'echo',
                "match_key": zenoh.KeyExpr(msg_data),
            }
        elif sample.payload[0:4] == b"UNLINK":
            request = {
                "type": 'unlink'
            }
        else:
            return
            
        if self.request_callback:
            self.request_callback(request)
        else:
            self.requests_queue.put(request)
        return

    def send_response(self, msg_type:str, web_id:uuid.UUID, edge_id:int, status:str):
        self._responses_publisher.put(
            msg_type.encode('utf-8') + b"\x00" +
            web_id.bytes + 
            struct.pack("<L", edge_id) +
            status.encode('utf-8') + b"\x00"
        )

    def list_produced_keys(self, keys_to_publish:list[zenoh.KeyExpr]):
        for key in keys_to_publish:
            self._producers_publisher.put(key)


    def list_consumed_keys(self, keys_to_publish:list[zenoh.KeyExpr]):
        for key in keys_to_publish:
            self._consumers_publisher.put(key)



class ZvezWeaverGlobalChannels:
    def __init__(self,session: zenoh.Session):
        self.requests_queue = queue.Queue()
        self.responses_queue = queue.Queue()
        self.producers_queue = queue.Queue()
        self.consumers_queue = queue.Queue()

        self._responses_subscriber = session.declare_subscriber(GLOBAL_RESPONSES_KEY, self.response_handler)
        self._producers_subscriber = session.declare_subscriber(GLOBAL_PRODUCERS_KEY, self.producer_handler)
        self._consumers_subscriber = session.declare_subscriber(GLOBAL_CONSUMERS_KEY, self.consumer_handler)

        self._requests_publisher = session.declare_publisher(GLOBAL_REQUESTS_KEY)

    def send_link_request(self, web_id:uuid.UUID, edge_id:int, producer_key:zenoh.KeyExpr, consumer_key:zenoh.KeyExpr):
        self._requests_publisher.put(
            b"LINK" + b"\x00" +
            web_id.bytes + 
            struct.pack("<L", edge_id) +
            str(producer_key).encode('utf-8') + b"\x00" +
            str(consumer_key).encode('utf-8') + b"\x00"
        )

    def response_handler(self, sample):
        msg_str = sample.payload.decode()
        msg_type = msg_str[0:msg_str.index("\x00")]
        msg_data = msg_str[msg_str.index("\x00")+1:]

        #TODO everything
        request = None
            
        self.requests_queue.put(request)
        return

    def producer_handler(self, sample):
        self.producers_queue.put(sample)

    def consumer_handler(self, sample):
        self.consumers_queue.put(sample)
