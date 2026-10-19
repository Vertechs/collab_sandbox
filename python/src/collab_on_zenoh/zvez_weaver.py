import threading
import uuid
import zenoh
import random
import numpy
import datetime as dt
import struct
import time
import logging

from typing import Callable
from dataclasses import dataclass

import collab_on_zenoh.zvez_global_channels as gc
from collab_on_zenoh.zvez_dataclasses import *

log = logging.getLogger(__name__)


class ZvezWeb:
    def __init__(self, web_id: uuid.UUID):
        self.web_id = web_id
        self.edges: list[ZvezEdge] = []
        self.edge_ids: set[int] = set()

    def get_new_edge_id(self):
        new_id = max(self.edge_ids) + 1 if self.edge_ids else 0
        if new_id > 2**32 - 1:
            return None
        self.edge_ids.add(new_id)
        return new_id

    def create_new_edge(self, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr):
        edge_id = self.get_new_edge_id()
        if edge_id is None:
            return None
        edge = ZvezEdge(edge_id, consumer_key, producer_key)
        self.edges.append(edge)
        return edge

    # TODO dont actually need these, handled in global channel functions
    def create_packet_teardown(self):
        return b'TEARDOWN'+b'x\00'+self.web_id.bytes

    def create_packet_edge_delete(self, edge: ZvezEdge):
        return b'REMOVE'+b'x\00'+self.web_id.bytes+struct.pack('<I', edge.edge_id)

    def create_packet_link(self, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr):
        edge_id = self.get_new_edge_id()
        if edge_id is None:
            return None
        return b'LINK'+b'x\00'+self.web_id.bytes+struct.pack('<I', edge_id)+str(producer_key).encode('utf-8') + b"\x00" +str(consumer_key).encode('utf-8') + b"\x00"

class ZvezWeaver:
    def __init__(self) -> None:
    
            self._stop = threading.Event()

            self.session = zenoh.open(zenoh.Config())
            self.global_channels = gc.ZvezWeaverGlobalChannels(self.session)

    def close(self):
        self._stop.set()

        self.global_channels.close()

        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    


    