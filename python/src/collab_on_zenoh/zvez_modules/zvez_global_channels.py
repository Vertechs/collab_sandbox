import zenoh
import queue
import uuid
import struct
import asyncio
import logging

from dataclasses import dataclass
from collections.abc import Callable

from .zvez_dataclasses import *

GLOBAL_REQUESTS_KEY = "@zvez/global/requests"
GLOBAL_RESPONSES_KEY = "@zvez/global/responses"
GLOBAL_PRODUCERS_KEY = "@zvez/global/producers"
GLOBAL_CONSUMERS_KEY = "@zvez/global/consumers"
GLOBAL_BOOTSTRAP_KEY = "@zvez/global/bootstrap"

MAX_REQUESTS = 20 #TODO don't hardcode this

PORT_TYPES = ['P','C','A']

log = logging.getLogger(__name__)

class ZvezNodeGlobalChannels:
    '''
    Owns the actual subscribers and publishers for all global channels
    Handling messages, tracking active produce/consume ports, etc.
    is all handled in the node class

    Essentially just a wrapper/formatter so that nodes can use JSON and string data
    and so everyone always has the same global channel definitions

    '''

    def __init__(self,session: zenoh.Session):
        self.responses_queue = queue.Queue()

        self._requests_subscriber = session.declare_subscriber(GLOBAL_REQUESTS_KEY, zenoh.handlers.RingChannel(MAX_REQUESTS))
        
        self._responses_publisher = session.declare_publisher(GLOBAL_RESPONSES_KEY)
        self._producers_publisher = session.declare_publisher(GLOBAL_PRODUCERS_KEY)
        self._consumers_publisher = session.declare_publisher(GLOBAL_CONSUMERS_KEY)

        self._bootstrap_subscriber = session.declare_subscriber(GLOBAL_BOOTSTRAP_KEY, zenoh.handlers.RingChannel(MAX_REQUESTS))
        self._bootstrap_publisher = session.declare_publisher(GLOBAL_BOOTSTRAP_KEY)


    def recv_request(self) -> dict | None:
        # pop next message out of ring buffer, process to standard JSON request format, and return
        sample = self._requests_subscriber.try_recv()
        if not sample:
            return None

        #TODO better format checking and logging
        msg_str = sample.payload.to_bytes()
        msg_type = msg_str[0:msg_str.index(b"\x00")]
        msg_data = msg_str[msg_str.index(b"\x00")+1:]

        log.log(logging.DEBUG, "Processing request: type={}, data={}".format(msg_type, msg_data))
        #TODO add checks for valid format, break into functions
        if msg_type == b"LINK":
            # check after web and edge ID, may contain null bytes
            e1 = msg_data[20:].index(b"\x00") + 20
            request = {
                "type": RequestType.LINK,
                "webID": uuid.UUID(bytes=struct.unpack("16s", msg_data[0:16])[0]),
                "edgeID": struct.unpack("<L", msg_data[16:20])[0],
                "consumer_key": zenoh.KeyExpr(str(msg_data[20:e1], 'utf-8').strip('x\00')),
                "producer_key": zenoh.KeyExpr(str(msg_data[e1+1:], 'utf-8').strip('x\00')),
            }
        elif msg_type == b"ECHO":
            request = {
                "type": RequestType.ECHO,
                "port_type": PortType(msg_data[0:1].decode('utf-8')),
                "match_key": zenoh.KeyExpr(msg_data[1:].decode('utf-8').strip('x\00')),
            }
        elif msg_type == b"UNLINK":
            #TODO format request
            request = {
                "type": RequestType.UNLINK
            }
        else:
            log.log(logging.DEBUG, "Unknown request type: {}".format(msg_type))
            return None
            

        return request

    def send_response(self, msg_type:str, web_id:uuid.UUID, edge_id:int, status:str):
        self._responses_publisher.put(
            msg_type.encode('utf-8') + b"\x00" +
            web_id.bytes + 
            struct.pack("<L", edge_id) +
            status.encode('utf-8') + b"\x00"
        )

    def list_produced_keys(self, keys_to_publish:list[zenoh.KeyExpr]):
        # TODO publish things besides just the key
        for key in keys_to_publish:
            self._producers_publisher.put(bytes(str(key), 'utf-8'))


    def list_consumed_keys(self, keys_to_publish:list[zenoh.KeyExpr]):
        # TODO publish things besides just the key
        for key in keys_to_publish:
            self._consumers_publisher.put(bytes(str(key), 'utf-8'))

    def send_shutdown_notification(self, key: zenoh.KeyExpr):
        # node should send for all produced keys before shutting down
        shutdown_message = bytes(BootstrapStatus.SHUTDOWN, 'utf-8') + b'x\00' + bytes(str(key), 'utf-8')
        self._bootstrap_publisher.put(shutdown_message)

    def __exit__(self, exc_type, exc_val, exc_tb):
        log.log(logging.DEBUG, "Closing global channels")
        self._requests_subscriber.undeclare()
        self._responses_publisher.undeclare()
        self._producers_publisher.undeclare()
        self._consumers_publisher.undeclare()
        self._bootstrap_publisher.undeclare()
        self._bootstrap_subscriber.undeclare()

    def __enter__(self):
        return self

    def close(self):
        self.__exit__(None, None, None)


class ZvezWeaverGlobalChannels:
    def __init__(self,session: zenoh.Session):
        self._responses_subscriber = session.declare_subscriber(GLOBAL_RESPONSES_KEY,zenoh.handlers.RingChannel(MAX_REQUESTS))
        self._producers_subscriber = session.declare_subscriber(GLOBAL_PRODUCERS_KEY,zenoh.handlers.RingChannel(MAX_REQUESTS))
        self._consumers_subscriber = session.declare_subscriber(GLOBAL_CONSUMERS_KEY,zenoh.handlers.RingChannel(MAX_REQUESTS))

        self._requests_publisher = session.declare_publisher(GLOBAL_REQUESTS_KEY)

    def send_link_request(self, web_id:uuid.UUID, edge_id:int, producer_key:zenoh.KeyExpr, consumer_key:zenoh.KeyExpr):
        log.log(logging.DEBUG, f"Sending link request: web_id={web_id}, edge_id={edge_id}, producer_key={producer_key}, consumer_key={consumer_key}")
        msg = b"LINK" + b"\x00" + \
                    web_id.bytes + \
                    struct.pack("<L", edge_id) + \
                    str(producer_key).encode('utf-8') + b"\x00" + \
                    str(consumer_key).encode('utf-8') + b"\x00"
        log.log(logging.DEBUG, f"Link request message: {msg}")
        self._requests_publisher.put(msg)

    def send_echo_request(self, match_key: zenoh.KeyExpr, port_type: str):
        log.log(logging.DEBUG, f"Sending echo request: match_key={match_key}, port_type={port_type}")
        if port_type not in PORT_TYPES:
            return -1
        self._requests_publisher.put(
            b"ECHO" + b"\x00" +
            port_type.encode('utf-8') +
            str(match_key).encode('utf-8') + b"\x00"
        )

    def read_response(self):
        sample = self._responses_subscriber.try_recv()
        if sample:
            msg_str = sample.payload.to_bytes()
            msg_type = msg_str[0:msg_str.index(b"\x00")]
            msg_data = msg_str[msg_str.index(b"\x00")+1:]
            log.log(logging.DEBUG, "Reading response: type={}, data={}".format(msg_type, msg_data))
            #TODO parsing this by message type

            return {'type': msg_type, 'data': msg_data}
        return None

    def read_producer(self) -> str | None:
        #TODO handling more than just key
        sample = self._producers_subscriber.try_recv()
        if sample:
            log.log(logging.DEBUG, "Reading producer: {}".format(sample.payload.to_string()))
            return sample.payload.to_string()
        else:
            log.log(logging.DEBUG, "No producer keys available")
        return None

    def read_consumer(self) ->str | None:
        #TODO handling more than just key
        sample = self._consumers_subscriber.try_recv()
        if sample:
            log.log(logging.DEBUG, "Reading consumer: {}".format(sample.payload.to_string()))
            return sample.payload.to_string()
        else:
            log.log(logging.DEBUG, "No consumer keys available")
        return None


    def __exit__(self, exc_type, exc_val, exc_tb):
        log.log(logging.DEBUG, "Closing global channels")
        self._requests_publisher.undeclare()
        self._responses_subscriber.undeclare()
        self._producers_subscriber.undeclare()
        self._consumers_subscriber.undeclare()

    def __enter__(self):
        return self

    def close(self):
        self.__exit__(None, None, None)