import threading
import zenoh
import random
import numpy
import datetime as dt
import struct
import time
import logging

from functools import partial
from collections.abc import Callable
from dataclasses import dataclass

from . import zvez_global_channels as gc
from .zvez_dataclasses import *

CONSUMER_RING_SIZE = 20  # TODO don't hardcode this
GLOBAL_INTERVAL_DEFAULT = 2.0  # seconds also don't hardcode this
CONSUMER_INTERVAL = (
    0.01  # TODO don't hardcode, see comment for better thread scheduling
)
PRODUCER_INTERVAL = 0.01  # TODO same

log = logging.getLogger(__name__)


class ZvezNode:
    """Owns producer and consumer ports
    Handles global channel messages, but through global channel translator class
    """

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._global_thread: threading.Thread | None = None
        self._consume_thread: threading.Thread | None = None
        self._produce_thread: threading.Thread | None = None

        self.producers: dict[zenoh.KeyExpr, ZvezProducer] = {}
        self.consumers: dict[zenoh.KeyExpr, ZvezConsumer] = {}
        self.edges: list[ZvezEdge] = []

        self.session = zenoh.open(zenoh.Config())
        self.global_channels = gc.ZvezNodeGlobalChannels(self.session)
        self.global_channels_tick_interval = GLOBAL_INTERVAL_DEFAULT

    # =============
    # Lifecyle for Session and Global Channel Threads
    # =============
    def start(self):
        if self._global_thread is not None:
            return
        self._global_thread = threading.Thread(
            target=self._process_global_channels,
            name=f"ZvezNodeGlobalChannelThread-{id(self)}",
            daemon=True,
        )

        self._consume_thread = threading.Thread(
            target=self._run_consumers,
            name=f"ZvezNodeConsumerThread-{id(self)}",
            daemon=True,
        )

        self._produce_thread = threading.Thread(
            target=self._run_producers,
            name=f"ZvezNodeProducerThread-{id(self)}",
            daemon=True,
        )

        self._global_thread.start()
        self._consume_thread.start()
        self._produce_thread.start()

    def close(self):
        self._stop.set()

        if (self._consume_thread is not None) and (
            self._consume_thread is not threading.current_thread()
        ):
            self._consume_thread.join()
        self._consume_thread = None

        if (self._produce_thread is not None) and (
            self._produce_thread is not threading.current_thread()
        ):
            self._produce_thread.join()
        self._produce_thread = None

        # stop global thread before closing subscriber/producers or the zenoh session
        if (self._global_thread is not None) and (
            self._global_thread is not threading.current_thread()
        ):
            self._global_thread.join()
        self._global_thread = None

        for producer_key in self.producers:
            self._deactivate_producer(producer_key)

        for consumer_key in self.consumers:
            self._deactivate_consumer(consumer_key)

        self.global_channels.close()

        self.session.close()

    def graceful_shutdown(self):
        for key in self.producers:
            self.global_channels.send_shutdown_notification(key)
        self.close()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # =========
    # Global Channel Handling
    # =========

    def _process_global_channels(self) -> None:
        """
        thread wrapper for global channel message handling
        user node classes should call start() as soon as possible
        """

        next_tick = time.monotonic()
        while not self._stop.is_set():
            self._process_global_request_single()

            next_tick += self.global_channels_tick_interval
            next_tick = max(
                next_tick, time.monotonic()
            )  # don't call back to back if steps are slow
            if self._stop.wait(max(0.0, next_tick - time.monotonic())):
                break

    def _process_global_request_single(self) -> None:
        """
        process and act on messages received on global channels
        executes one request at time
        global_channels starts a circular buffer so no guarantee that we will process all requests
        """

        try:
            request = self.global_channels.recv_request()
        except Exception as e:
            log.exception("Bad request received")
            return
        
        if not request:
            log.log(logging.DEBUG, "No request received")
            return

        # all echo requests
        match RequestType(request["type"]):
            case RequestType.ECHO:
                self._process_echo_request(request)
                return

            # link requests, handle depending on whether we are the producer or consumer
            case RequestType.LINK:
                log.log(logging.DEBUG, "Processing link request: producer_key={}, consumer_key={}".format(request["producer_key"], request["consumer_key"]))
                log.log(logging.DEBUG, "Producer keys: {}".format(list(self.producers.keys())))
                log.log(logging.DEBUG, "Consumer keys: {}".format(list(self.consumers.keys())))
                if request["producer_key"] in self.producers:
                    self._process_link_produce_request(request)
                elif request["consumer_key"] in self.consumers:
                    self._process_link_consume_request(request)
                return

            # unlink requests, handle depending on whether we are the producer or consumer
            case RequestType.UNLINK:
                # TODO
                return

            case _:
                log.log(
                    logging.DEBUG, "Unknown request type: {}".format(request["type"])
                )
                return

    def _process_echo_request(self, request: dict) -> None:
        log.log(
            logging.DEBUG,
            "Processing echo request: port_type={}, match_key={}".format(
                request["port_type"], request["match_key"]
            ),
        )
        matched_producers = [
            producer.key_expr
            for producer in self.producers.values()
            if request["match_key"].includes(producer.key_expr)
        ]
        matched_consumers = [
            consumer.key_expr
            for consumer in self.consumers.values()
            if request["match_key"].includes(consumer.key_expr)
        ]

        port_type = PortType(request["port_type"])

        if port_type in (PortType.PRODUCER, PortType.ALL):
            self.global_channels.list_produced_keys(matched_producers)
        if port_type in (PortType.CONSUMER, PortType.ALL):
            self.global_channels.list_consumed_keys(matched_consumers)

    def _process_link_produce_request(self, request: dict) -> None:
        log.log(
            logging.DEBUG,
            "Processing link produce request: producer_key={}, consumer_key={}".format(
                request["producer_key"], request["consumer_key"]
            ),
        )
        if self._activate_producer(request["producer_key"]):
            self.global_channels.send_response(
                "LINK", request["webID"], request["edgeID"], LinkStatus.OKAY
            )
        else:
            self.global_channels.send_response(
                "LINK", request["webID"], request["edgeID"], LinkStatus.FAIL
            )

    def _process_link_consume_request(self, request: dict) -> None:
        log.log(
            logging.DEBUG,
            "Processing link consume request: producer_key={}, consumer_key={}".format(
                request["producer_key"], request["consumer_key"]
            ),
        )
        if self._activate_consumer_key(
            request["consumer_key"], request["producer_key"]
        ):
            self.global_channels.send_response(
                "LINK", request["webID"], request["edgeID"], LinkStatus.OKAY
            )
        else:
            self.global_channels.send_response(
                "LINK", request["webID"], request["edgeID"], LinkStatus.FAIL
            )

    # =============
    # Producers
    # =============
    def register_producer(
        self,
        key: zenoh.KeyExpr,
        sample_generator: Callable[[], bytes] | None = None,
        sample_interval: float = 0.0,
    ):
        if key in self.producers:
            return
        self.producers[key] = ZvezProducer(
            key_expr=key,
            sample_generator=sample_generator,
            sample_interval=sample_interval,
        )

    def send_sample_now(self, producer_key: zenoh.KeyExpr, payload: bytes):
        # TODO synchronous for now, need to add RPI at link level
        producer = self.producers.get(producer_key)
        if producer is None or producer.publisher is None:
            # TODO logging
            return
        producer.publisher.put(payload)

    def _run_producers(self):
        while not self._stop.is_set():
            now = time.monotonic()

            # iterate over list copy to avoid dict changing size during loop
            for producer in list(self.producers.values()):
                self._producer_generate_sample(producer)

            # for now, just yield for 10ms
            # TODO can optimize response times for rate trigger with better thread timeouts and wake from _receive
            self._stop.wait(PRODUCER_INTERVAL)

    def _producer_generate_sample(self, producer: ZvezProducer):
        # if sample interval is 0, assume user triggered
        # TODO add producer types and queues maybe
        if (
            (producer.sample_interval > 0.0)
            and (producer.sample_generator is not None)
            and (producer.publisher is not None)
        ):
            # TODO race with deactivate, could call recently removed producer
            interval  = time.monotonic() - producer.last_generated
            if interval > producer.sample_interval:
                producer.last_generated = time.monotonic()
                sample_bytes = self._producer_generate_sample_safe(producer)
                if sample_bytes is not None:
                    producer.publisher.put(sample_bytes)

    def _producer_generate_sample_safe(self, producer):
        try:
            return producer.sample_generator()
        except Exception:
            log.exception(f"Consumer handler failed for {producer.key_expr}")
            return None

    def _deactivate_producer(self, key: zenoh.KeyExpr):
        if key in self.producers:
            producer = self.producers[key]
            if producer.publisher:
                producer.publisher.undeclare()
                producer.publisher = None

    def _activate_producer(self, key: zenoh.KeyExpr) -> bool:
        producer = self.producers.get(key)

        if producer is None:
            log.log(logging.DEBUG, "Producer not found for key: {}".format(key))
            return False
        if producer.publisher is not None:
            log.log(logging.DEBUG, "Producer already active for key: {}".format(key))
            return True
        
        try:
            producer.publisher = self.session.declare_publisher(producer.key_expr)
            log.log(logging.DEBUG, "Activated producer for key: {}".format(key))
            return True
        except (zenoh.ZError, KeyError) as e:
            log.log(logging.DEBUG, "Failed to activate producer for key: {} with error: {}".format(key, e))
            return False

    # =============
    # Consumers
    # =============
    def register_consumer(
        self,
        key: zenoh.KeyExpr,
        sample_handler: Callable[[zenoh.Sample], None] | None,
        sample_interval: float = 0.0,
        queue_type_str: str | None = None,
    ):
        # attempt to assign queue type from given arguements
        if queue_type_str is None:
            if sample_handler is not None:
                if sample_interval != 0.0:
                    queue_type = ConsumerType.RATE_TRIGGERED
                else:
                    queue_type = ConsumerType.RECV_TRIGGERED
            else:
                queue_type = ConsumerType.USER_TRIGGERED

        else:
            queue_type = ConsumerType(queue_type_str)

        match queue_type:
            case ConsumerType.RATE_TRIGGERED:
                queue_length: int = 1
            case ConsumerType.RECV_TRIGGERED:
                queue_length: int = 3  # TODO: 1 or not 1? callback could miss some, but will call back-to-back
            case _:
                queue_length: int = CONSUMER_RING_SIZE

        consumer = ZvezConsumer(
            key_expr=key, sample_handler=sample_handler, queue_type=queue_type
        )
        consumer.sample_queue = deque(maxlen=queue_length)
        consumer.sample_interval = sample_interval

        self.consumers[key] = consumer

    def read_sample_now(
        self, consumer_key: zenoh.KeyExpr, oldest: bool = True
    ) -> zenoh.Sample | None:
        """
        For when user node handles recieve queue, or called at any time to check for samples
        """
        # TODO better methods for accessing queue
        if consumer_key in self.consumers:
            consumer = self.consumers[consumer_key]
            if consumer.subscribers and consumer.sample_queue:
                if consumer.queue_type == ConsumerType.RATE_TRIGGERED:
                    return consumer.sample_queue[0]
                else:
                    if oldest:
                        return consumer.sample_queue.popleft()
                    else:
                        return consumer.sample_queue.pop()

        return None

    def _run_consumers(self):
        while not self._stop.is_set():
            now = time.monotonic()

            # iterate over list copy to avoid dict chaning size during loop
            for consumer in list(self.consumers.values()):
                self._consumer_handle_sample(consumer)

            # for now, just yield for 10ms
            # TODO can optimize response times for rate trigger with better thread timeouts and wake from _receive
            self._stop.wait(CONSUMER_INTERVAL)

    def _consumer_handle_sample(self, consumer):
        if consumer.sample_handler is None:
            return

        match consumer.queue_type:
            case ConsumerType.USER_TRIGGERED:
                return

            case ConsumerType.RATE_TRIGGERED:
                # check if time to update TODO: call this from an actual timer?
                interval = time.monotonic() - consumer.last_callback
                if consumer.sample_queue and (interval > consumer.sample_interval) and consumer.sample_interval > 0.0:
                    consumer.last_callback = time.monotonic()
                    self._consumer_handler_safe(consumer, consumer.sample_queue[0])

            case ConsumerType.RECV_TRIGGERED:
                # if any new samples, call callback immediately and pop sample out of queue
                if consumer.sample_queue:
                    self._consumer_handler_safe(
                        consumer, consumer.sample_queue.popleft()
                    )

    def _consumer_handler_safe(self, consumer: ZvezConsumer, sample: zenoh.Sample):
        if consumer.sample_handler:
            try:
                consumer.sample_handler(sample)
            except Exception:
                log.exception(f"Consumer handler failed for {consumer.key_expr}")

    def _activate_consumer_key(
        self, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr
    ) -> bool:

        # consumer key identifies the ZvezConsumer object in internal dict
        # producer key is what we actually subscribe to
        try:
            consumer = self.consumers[consumer_key]
            # TODO don't hardcode ring channel, need some QOS or similar
            consumer.subscribers[producer_key] = self.session.declare_subscriber(
                producer_key,
                partial(self._consumer_received, consumer_key=consumer_key),
            )

            return True
        except (zenoh.ZError, KeyError) as e:
            # TODO logging
            return False

    def _consumer_received(self, sample: zenoh.Sample, consumer_key: zenoh.KeyExpr):
        """
        Callback registered to all zenoh subscribers, add sample to internal queue
        """
        if consumer_key in self.consumers:
            consumer = self.consumers[consumer_key]
            if consumer.sample_queue is not None:
                consumer.sample_queue.append(sample)

    def _deactivate_consumer_key(
        self, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr
    ):
        if consumer_key in self.consumers:
            consumer = self.consumers[consumer_key]
            subscriber = consumer.subscribers.pop(producer_key, None)
            if subscriber is not None:
                subscriber.undeclare()
                return True
        return False

    def _deactivate_consumer(self, key: zenoh.KeyExpr):
        if key in self.consumers:
            consumer = self.consumers[key]

            for subscriber in consumer.subscribers.values():
                subscriber.undeclare()

            # clear after undeclare in case callbacks called while deactivating
            consumer.sample_queue.clear()
            consumer.subscribers.clear()
