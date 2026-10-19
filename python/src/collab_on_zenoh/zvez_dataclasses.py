import threading
import uuid
import zenoh
import random
import numpy
import datetime as dt
import struct
import time

from typing import Callable
from dataclasses import dataclass

# web structs

@dataclass
class ZvezEdge:
    edge_id: int
    consumer_key: zenoh.KeyExpr
    producer_key: zenoh.KeyExpr

# node structs

@dataclass
class ZvezProducer:
    key_expr: zenoh.KeyExpr
    data_struct: str | None = None
    description: str | None = None
    publisher: zenoh.Publisher | None = None
    packet_interval: float = 60.0

@dataclass
class ZvezConsumer:
    key_expr: zenoh.KeyExpr
    data_struct: str | None = None
    description: str | None = None
    subscriber: zenoh.Subscriber | None = None
    packet_handler: Callable[[zenoh.Sample], None] | None = None


# global channel messages

@dataclass #TODO implement as class
class ZvezRequestLink:
    def __init__(self, web_id: uuid.UUID, edge_id: int, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr):
        self.web_id = web_id # TODO uuid OR unique string
        self.edge_id = edge_id
        self.consumer_key = consumer_key
        self.producer_key = producer_key