import threading
import uuid
import zenoh
import random
import numpy
import datetime as dt
import struct
import time
from collections import deque

from collections.abc import Callable
from enum import Enum
from dataclasses import dataclass, field


# enums

class RequestType(str, Enum):
    ECHO = "ECHO"
    LINK = "LINK"
    UNLINK = "UNLINK"


class PortType(str, Enum):
    PRODUCER = "P"
    CONSUMER = "C"
    ALL = "A"


class LinkStatus(str, Enum):
    OKAY = "OKAY"
    FAIL = "FAIL"

class BootstrapStatus(str, Enum):
    SHUTDOWN = "SHUTDOWN"
    HELP = "HELP"

class ConsumerType(str, Enum):
    USER_TRIGGERED = 'user'
    RATE_TRIGGERED = 'rate'
    RECV_TRIGGERED = 'receive'




# web structs


@dataclass
class ZvezEdge:
    web_id : uuid.UUID
    edge_id: int #TODO maybe not needed? Key pair should be unique
    consumer_key: zenoh.KeyExpr
    producer_key: zenoh.KeyExpr


# node structs


@dataclass
class ZvezProducer:
    # port information
    key_expr: zenoh.KeyExpr
    data_struct: str | None = None
    description: str | None = None

    # zenoh
    publisher: zenoh.Publisher | None = None

    # handlers
    last_generated: float = 0.0
    sample_interval: float = 0.0
    sample_generator: Callable[[], bytes] | None = None


@dataclass
class ZvezConsumer:
    # port information
    key_expr: zenoh.KeyExpr
    data_struct: str | None = None
    description: str | None = None

    # zenoh
    subscribers: dict[zenoh.KeyExpr, zenoh.Subscriber] = field(default_factory=dict)

    # handlers
    queue_type: ConsumerType | None = None
    last_callback : float = 0.0
    sample_interval: float = 0.0
    sample_queue : deque[zenoh.Sample] = field(default_factory=deque)
    sample_handler: Callable[[zenoh.Sample], None] | None = None


# global channel messages


@dataclass  # TODO implement as class
class ZvezRequestLink:
    def __init__(
        self,
        web_id: uuid.UUID,
        edge_id: int,
        consumer_key: zenoh.KeyExpr,
        producer_key: zenoh.KeyExpr,
    ):
        self.web_id = web_id  # TODO uuid OR unique string
        self.edge_id = edge_id
        self.consumer_key = consumer_key
        self.producer_key = producer_key

