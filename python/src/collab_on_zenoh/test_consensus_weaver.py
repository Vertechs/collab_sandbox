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

import collab_on_zenoh.zvez_modules.zvez_global_channels as gc
from collab_on_zenoh.zvez_modules.zvez_node import *
from collab_on_zenoh.zvez_modules.zvez_weaver import *

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

class ZvezConsWeaver:
    def __init__(self, parent_key):
        self.parent_key = parent_key
        self.zvez_weaver = ZvezWeaver()
        self.zvez_weaver.__init__()

        self.zvez_weaver.global_channel_interval = 1.0

        self.zvez_weaver.start()

    def spin(self):

        with self.zvez_weaver:
            while True:
                time.sleep(1)

    def start_full_web(self):
        web_id = self.zvez_weaver.init_web()

        for consumer_key in self.zvez_weaver.known_consumers:
            for producer_key in self.zvez_weaver.known_producers:
                print("adding {} -> {}".format(producer_key, consumer_key))
                self.zvez_weaver.add_edge_to_web(web_id, consumer_key, producer_key)

        
    def discovery(self, listening_time: float = 5.0):
        self.zvez_weaver.auto_discovery(zenoh.KeyExpr(self.parent_key).join("**"), listening_time)

        stop_time = time.monotonic() + listening_time

        last_lens = [0,0]

        while time.monotonic() < stop_time:
            if len(self.zvez_weaver.known_producers) > last_lens[0]:
                last_lens[0] = len(self.zvez_weaver.known_producers)
                last_added = list(self.zvez_weaver.known_producers.values())[-1]
                print(f"New producers: {last_added}")

            if len(self.zvez_weaver.known_consumers) > last_lens[1]:
                last_lens[1] = len(self.zvez_weaver.known_consumers)
                last_added = list(self.zvez_weaver.known_consumers.values())[-1]
                print(f"New consumers: {last_added}")

    def stop(self):
        self.zvez_weaver.close()

if __name__ == "__main__":
    consensus_weaver = ZvezConsWeaver("@zvez/consensus")
    consensus_weaver.discovery()
    consensus_weaver.start_full_web()
    consensus_weaver.stop()
