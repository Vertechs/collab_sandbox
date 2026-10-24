import json
import logging
import time
import threading
import zenoh
import random
import numpy as np
import datetime as dt
import struct
import queue
import threading
import time
import logging

import argparse

import collab_on_zenoh.zvez_modules.zvez_global_channels as gc
from collab_on_zenoh.zvez_modules.zvez_node import *
from collab_on_zenoh.zvez_modules.zvez_weaver import *
from collab_on_zenoh.zvez_modules.zvez_dataclasses import *

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

STATE_SHAPE = (4, 1)
STATE_SCALE = 1000

WIRE_DTYPE = np.dtype("<f4")


class ZvezConsNode:
    def __init__(self, domain: zenoh.KeyExpr, node_num: int):
        self.zvez_node = ZvezNode()
        self.zvez_node.__init__()

        self.node_num = node_num
        self.parent_key = domain

        self.state = np.zeros((STATE_SHAPE), dtype=np.float32)
        self.rate = 0.001

        self.zvez_node.register_producer(
            key=self.parent_key.join(f"{self.node_num}/state"),
            sample_generator=self.get_state_as_bytes,
            sample_interval=0.1,
        )

        self.zvez_node.register_consumer(
            key=self.parent_key.join(f"{self.node_num}/neighbor_states"),
            sample_handler=self.process_sample,
            sample_interval=0.1,
        )

        for c in self.zvez_node.consumers.values():
            assert c.queue_type == ConsumerType.RATE_TRIGGERED
            assert c.sample_interval > 0.0

    def get_state_as_bytes(self):
        state_bytes = np.ascontiguousarray(self.state, dtype=WIRE_DTYPE)
        log.log(logging.DEBUG, "Generating state as bytes {}".format(state_bytes))

        return state_bytes.tobytes()

    def process_sample(self, sample: zenoh.Sample):
        log.log(
            logging.DEBUG,
            f"Processing sample from key: {sample.key_expr} data:{sample.payload.to_bytes()}",
        )
        neighbor_state = np.frombuffer(sample.payload.to_bytes(), dtype=WIRE_DTYPE)
        neighbor_state = neighbor_state.reshape(self.state.shape)
        self.state = self.state * (1 - self.rate) + neighbor_state * self.rate

    def spin(self):
        with self.zvez_node:
            try:
                while True:
                    print(self.state)
                    time.sleep(1)

            except KeyboardInterrupt:
                print("EXITING NODE PROGRAM")
                self.zvez_node.graceful_shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("node_num", type=int, default=None)
    args = parser.parse_args()

    node_num = args.node_num if args.node_num is not None else np.random.randint(0, 100)

    consensus_node = ZvezConsNode(
        zenoh.KeyExpr("@zvez/consensus"), node_num=node_num
    )
    consensus_node.state = np.random.random(consensus_node.state.size) * STATE_SCALE
    consensus_node.spin()

# (trap 'kill 0' INT TERM; for i in $(seq 1 10); do python3 test_consensus_node.py $i & sleep $(awk -v r=$RANDOM 'BEGIN{print r/32768*0.5}'); done; wait)