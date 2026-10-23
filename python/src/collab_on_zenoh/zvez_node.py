import threading
from typing import Callable
import zenoh
import random
import numpy
import datetime as dt
import struct
import time
import logging

from dataclasses import dataclass

import collab_on_zenoh.zvez_global_channels as gc
from collab_on_zenoh.zvez_dataclasses import *

CONSUMER_RING_SIZE = 20 #TODO don't hardcode this

log = logging.getLogger(__name__)


class ZvezNode:
    ''' Owns producer and consumer ports
        Handles global channel messages, but through global channel translator class
        
        Inherited or included in other node classes
    
    '''

    def __init__(self) -> None:
            self._stop = threading.Event()

            self.producers: dict[zenoh.KeyExpr, ZvezProducer] = {}
            self.consumers: dict[zenoh.KeyExpr, ZvezConsumer] = {}

            self.session = zenoh.open(zenoh.Config())
            self.global_channels = gc.ZvezNodeGlobalChannels(self.session)

    #=========
    # Global Channel Handling
    #=========

    def process_globals(self) -> None:
        # ACT on request from global channel queue

        request = self.global_channels.recv_request()
        if not request:
            log.log(logging.DEBUG, "No request received")
            return

        if request['type'] == 'echo':
            log.log(logging.DEBUG, "Processing echo request: port_type={}, match_key={}".format(request['port_type'], request['match_key']))
            matched_producers = [producer.key_expr for producer in self.producers.values() if request['match_key'].includes(producer.key_expr)]
            matched_consumers = [consumer.key_expr for consumer in self.consumers.values() if request['match_key'].includes(consumer.key_expr)]

            if request['port_type'] == 'P' or request['port_type'] == 'A':
                self.global_channels.list_produced_keys(matched_producers)
            if request['port_type'] == 'C' or request['port_type'] == 'A':
                self.global_channels.list_consumed_keys(matched_consumers)

        elif request['type'] == 'link':
            log.log(logging.DEBUG, "Processing link request, producer_key={}, consumer_key={}".format(request['producer_key'], request['consumer_key']))
            if request['producer_key'] in self.producers:
                if(self.activate_producer(request['producer_key'])):
                    self.global_channels.send_response('LINK', request['webID'], request['edgeID'], 'OKAY')
                else:
                    self.global_channels.send_response('LINK', request['webID'], request['edgeID'], 'FAIL')
                    
            elif request['consumer_key'] in self.consumers:
                if(self.activate_consumer(request['consumer_key'], request['producer_key'])):
                    self.global_channels.send_response('LINK', request['webID'], request['edgeID'], 'OKAY')
                else:
                    self.global_channels.send_response('LINK', request['webID'], request['edgeID'], 'FAIL')

        else:
            log.log(logging.DEBUG, "Unknown request type: {}".format(request['type']))
            return

    # =============
    # Producers
    # =============
    def register_producer(self, key: zenoh.KeyExpr):
        if key in self.producers:
            return
        producer = ZvezProducer(key_expr=key)
        self.producers[key] = producer

    def activate_producer(self, key: zenoh.KeyExpr) -> bool:
        try:
            producer = self.producers[key]
            producer.publisher = self.session.declare_publisher(producer.key_expr)
            return True
        except zenoh.ZError or KeyError as e:
            #TODO logging
            return False

    def send_sample_now(self, producer_key: zenoh.KeyExpr, payload: bytes):
        # TODO synchronous for now, need to add RPI at link level
        producer = self.producers.get(producer_key)
        if producer is None or producer.publisher is None:
            # TODO logging
            return
        producer.publisher.put(payload)

    def deactivate_producer(self, key: zenoh.KeyExpr):
        if key in self.producers:
            producer = self.producers[key]
            if producer.publisher:
                producer.publisher.undeclare()
                producer.publisher = None


    # =============
    # Consumers
    # =============
    def register_consumer(self, key: zenoh.KeyExpr, packet_handler: Callable[[zenoh.Sample], None] | None):
        #TODO don't need packet handler?
        consumer = ZvezConsumer(key_expr=key, packet_handler=packet_handler)
        self.consumers[key] = consumer

    def activate_consumer(self, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr) -> bool:
        try:
            consumer = self.consumers[consumer_key]
            #TODO don't hardcode ring channel, need some QOS or similar
            consumer.subscriber = self.session.declare_subscriber(producer_key, zenoh.handlers.RingChannel(CONSUMER_RING_SIZE))
            return True
        except zenoh.ZError or KeyError as e:
            #TODO logging
            return False

    def read_sample_now(self, consumer_key: zenoh.KeyExpr):
        # TODO better methods for accessing queue
        if consumer_key in self.consumers:
            consumer = self.consumers[consumer_key]
            if consumer.subscriber:
                sample = consumer.subscriber.try_recv()
                if sample:
                    return sample.payload
        return None

    def deactivate_consumer(self, key: zenoh.KeyExpr):
        if key in self.consumers:
            consumer = self.consumers[key]
            if consumer.subscriber:
                consumer.subscriber.undeclare()
                consumer.subscriber = None


    # =============
    # Session
    # =============
    def close(self):
        self._stop.set()

        for producer_key in self.producers:
            self.deactivate_producer(producer_key)

        for consumer_key in self.consumers:
            self.deactivate_consumer(consumer_key)

        self.global_channels.close()

        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    
    

    