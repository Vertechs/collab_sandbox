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

TRACE_LEVEL = 5
# enums
# TODO organize these better and decide on a standard for on-wire text
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

class LinkHealth(str, Enum):
    INIT = "INIT" # no link request sent yet
    OKAY = "OKAY" # link is established and nodes communicating
    FAILED = "FAIL" # link was attempted but could not be created
    REQUESTED = "RQST" # link request has been sent, no response yet
    REMOVED = "UNLK" # unlink request has been sent and successfully processed
    REM_PENDING = "REUL" # unlink request has been sent but not yet processed


# web structs

@dataclass
class ZvezEdge:
    web_id : uuid.UUID
    edge_id: int #TODO maybe not needed? Key pair should be unique
    consumer_key: zenoh.KeyExpr
    producer_key: zenoh.KeyExpr
    health: LinkHealth 


# node structs


@dataclass
class ZvezNodeProducer:
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
class ZvezNodeConsumer:
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

@dataclass
class ZvezWebPortEntry:
    # port information
    key_expr: zenoh.KeyExpr
    data_struct: str | None = None
    description: str | None = None

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

