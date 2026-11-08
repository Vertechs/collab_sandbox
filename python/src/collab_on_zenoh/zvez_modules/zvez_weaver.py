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
from collections import deque
from dataclasses import dataclass

from . import zvez_global_channels as gc
from .zvez_dataclasses import *

log = logging.getLogger(__name__)

WEAVER_MAX_PENDING_REQUESTS = 100

class ZvezWeb:
    # almost a dataclass, holds all edges in a list
    # methods to handle edge creation and ID management
    def __init__(self, web_id: uuid.UUID):
        self.web_id = web_id
        self.edges: list[ZvezEdge] = []
        self.edge_ids: set[int] = set() #TODO why have this

    def __iter__(self):
        return iter(self.edges)

    def get_new_edge_id(self):
        # TODO IDs maybe not needed, to and from ports should be unique
        new_id = max(self.edge_ids) + 1 if self.edge_ids else 0
        if new_id > 2**32 - 1:
            return None
        self.edge_ids.add(new_id)
        return new_id

    def create_new_edge(self, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr):
        edge_id = self.get_new_edge_id()
        if edge_id is None:
            return None
        edge = ZvezEdge(self.web_id, edge_id, consumer_key, producer_key, LinkHealth.INIT)
        self.edges.append(edge)
        return edge

    def remove_edge(self, edge: ZvezEdge):
        if edge in self.edges:
            self.edges.remove(edge)
            self.edge_ids.discard(edge.edge_id)

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
            self.global_channel_interval = 0.1
            self._global_channel_thread = None

            self.webs: dict[uuid.UUID, ZvezWeb] = {}
            self.known_producers: dict[zenoh.KeyExpr, ZvezWebPortEntry] = {}
            self.known_consumers: dict[zenoh.KeyExpr, ZvezWebPortEntry] = {}

            #TODO create request queue and handling data

    def close(self):
        self._stop.set()

        # stop global thread before closing subscriber/producers or the zenoh session
        if (self._global_channel_thread is not None) and (
            self._global_channel_thread is not threading.current_thread()
        ):
            self._global_channel_thread.join()
        self._global_channel_thread = None
        
        self.global_channels.close()

        self.session.close()

    def start(self):
        if self._global_channel_thread is not None:
            return

        self._global_channel_thread = threading.Thread(
            target=self._process_global_channels,
            name=f"ZvezWeaverGlobalChannelThread-{id(self)}",
            daemon=True,
        )

        self._global_channel_thread.start()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # =====
    # Global Channels
    # =====

    def _process_global_channels(self) -> None:
        next_tick = time.monotonic()

        while not self._stop.is_set():
            # Implement processing logic for global channels here
            self._process_global_consumer_single()
            self._process_global_producer_single()
            self._process_global_response_single()

            next_tick += self.global_channel_interval
            next_tick = max(
                next_tick, time.monotonic()
            )  # don't call back to back if steps are slow
            if self._stop.wait(max(0.0, next_tick - time.monotonic())):
                break


    def _send_global_request(self, request) -> None:
        # add and pop from pending queue
        pass


    def _process_global_response_single(self) -> None:
        try:
            response = self.global_channels.recv_response()
        except Exception as e:
            log.exception("Bad response received")
            return

        if not response:
            log.log(logging.DEBUG, "No response received")
            return

        # else
        log.log(logging.DEBUG, "Response received: %s", response)

        # TODO this is not correct, will have response from both ports, need to check both
        if response['type'] == RequestType.LINK:
           for edge in self.webs[response['webID']]:
               if edge.edge_id == response['edgeID']:
                   edge.health = LinkHealth(response['status'])


    def _process_global_producer_single(self) -> None:
        try:
            producer_entry = self.global_channels.recv_producer()
        except Exception as e:
            log.exception("Bad producer received")
            return

        if not producer_entry:
            log.log(logging.DEBUG, "No producer received")
            return

        # else
        log.log(logging.DEBUG, "Producer received: %s", producer_entry)

        self.known_producers[producer_entry['key']] = ZvezWebPortEntry(
            key_expr=zenoh.KeyExpr(producer_entry['key'])
        )


    def _process_global_consumer_single(self) -> None:
        try:
            consumer_entry = self.global_channels.recv_consumer()
        except Exception as e:
            log.exception("Bad consumer received")
            return

        if not consumer_entry:
            log.log(logging.DEBUG, "No consumer received")
            return

        # else
        log.log(logging.DEBUG, "Consumer received: %s", consumer_entry)

        self.known_consumers[consumer_entry['key']] = ZvezWebPortEntry(
            key_expr=zenoh.KeyExpr(consumer_entry['key'])
        )

    def auto_discovery(self, match_key: zenoh.KeyExpr, listening_time: float = 5.0):
        self.global_channels.send_echo_request(match_key, PortType.ALL)
        # global channel thread will process all messages, don't need to do anything here
    
    def init_web(self):
        web_id = uuid.uuid4()
        self.webs[web_id] = ZvezWeb(web_id)
        return web_id

    def add_edge_to_web(self, web_id: uuid.UUID, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr):
        if web_id not in self.webs:
            log.log(logging.ERROR, "Web ID not found")
            return False

        edge = self.webs[web_id].create_new_edge(consumer_key, producer_key)
        if edge is None:
            log.log(logging.ERROR, "Failed to create new edge, max edges reached")
            return False

        self.global_channels.send_link_request(web_id, edge.edge_id, consumer_key, producer_key)
        return True
