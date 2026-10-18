import threading
from typing import Callable
import zenoh
import random
import numpy
import datetime as dt
import struct
import time

from dataclasses import dataclass

import collab_on_zenoh.global_channels as gc

@dataclass
class ZvezProducer:
    key_expr: zenoh.KeyExpr
    data_struct: str | None = None
    description: str | None = None
    publisher: zenoh.Publisher | None = None


@dataclass
class ZvezConsumer:
    key_expr: zenoh.KeyExpr
    data_struct: str | None = None
    description: str | None = None
    subscriber: zenoh.Subscriber | None = None
    callback: Callable[[zenoh.Sample], None] | None = None


class ZvezNode:
    def __init__(self, domain:str) -> None:
            self.parent_key = "/".join((domain,"clock"))
    
            self._stop = threading.Event()

            self.producers: dict[str, ZvezProducer] = {}
            self.consumers: dict[str, ZvezConsumer] = {}

            self.session = zenoh.open(zenoh.Config())
            self.global_channels = gc.ZvezNodeGlobalChannels(self.session, self.global_callback)


    def global_callback(self, request):
        if request['type'] == 'echo':
            matched_producers = [producer.key_expr for producer in self.producers.values() if request['match_key'].includes(producer.key_expr)]
            matched_consumers = [consumer.key_expr for consumer in self.consumers.values() if request['match_key'].includes(consumer.key_expr)]

            self.global_channels.list_produced_keys(matched_producers)
            self.global_channels.list_consumed_keys(matched_consumers)
        
        elif request['type'] == 'link':
            if request['producer_key'] in self.producers:
                if(self.activate_producer(self.producers[request['producer_key']])):
                    self.global_channels.send_response('LINK', request['webID'], request['edgeID'], 'OKAY')
                else:
                    self.global_channels.send_response('LINK', request['webID'], request['edgeID'], 'FAIL')
                    
            elif request['consumer_key'] in self.consumers:
                if(self.activate_consumer(self.consumers[request['consumer_key']])):
                    self.global_channels.send_response('LINK', request['webID'], request['edgeID'], 'OKAY')
                else:
                    self.global_channels.send_response('LINK', request['webID'], request['edgeID'], 'FAIL')



    # =============
    # Producers
    # =============
    def register_producer(self, key: zenoh.KeyExpr):
        producer = ZvezProducer(key_expr=key)
        self.producers[str(key)] = producer

    def activate_producer(self, producer: ZvezProducer) -> bool:
        try:
            producer.publisher = self.session.declare_publisher(producer.key_expr)
            return True
        except zenoh.ZError as e:
            #TODO logging
            return False

    def deactivate_producer(self, producer: ZvezProducer):
        if producer.publisher:
            producer.publisher.undeclare()
            producer.publisher = None


    # =============
    # Consumers
    # =============
    def register_consumer(self, key: zenoh.KeyExpr, callback: Callable[[zenoh.Sample], None]):
        consumer = ZvezConsumer(key_expr=key, callback=callback)
        self.consumers[str(key)] = consumer

    def activate_consumer(self, consumer: ZvezConsumer) -> bool:
        try:
            consumer.subscriber = self.session.declare_subscriber(consumer.key_expr, consumer.callback)
            return True
        except zenoh.ZError as e:
            #TODO logging
            return False

    def deactivate_consumer(self, consumer: ZvezConsumer):
        if consumer.subscriber:
            consumer.subscriber.undeclare()
            consumer.subscriber = None


    # =============
    # Session
    # =============
    def close(self):
        self._stop.set()

        for producer in self.producers.values():
            self.deactivate_producer(producer)

        for consumer in self.consumers.values():
            self.deactivate_consumer(consumer)
            consumer.callback = None

        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    
    

    