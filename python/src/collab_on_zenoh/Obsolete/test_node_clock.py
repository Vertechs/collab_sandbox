import threading
import zenoh
import random
import numpy
import datetime as dt
import struct
import time
import logging

import collab_on_zenoh.zvez_modules.zvez_global_channels as gc
from collab_on_zenoh.zvez_modules.zvez_node import *
from collab_on_zenoh.zvez_modules.zvez_weaver import *

UTILITY_KEY = "@zvez/util"

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",)
log = logging.getLogger(__name__)

class ZvezClockNode(ZvezNode):
    def __init__(self, domain: zenoh.KeyExpr):
        super().__init__()

        self.parent_key = domain.join("clock")

        self.register_producer(self.parent_key.join("time_s"))
        self.register_producer(self.parent_key.join("time_ms"))

        self.register_consumer(self.parent_key.join("tick_now"), None)

    def spin(self):

        while not self._stop.is_set():
            ts = dt.datetime.now(dt.timezone.utc).timestamp()

            self.send_sample_now(self.parent_key.join("time_s"), struct.pack('<I', int(ts)))
            self.send_sample_now(self.parent_key.join("time_ms"), struct.pack('<I', int(ts%1.0 * 1000)))

            if self.read_sample_now(self.parent_key.join("tick_now")) is not None:
                print("Tick received!")

            print("Time: {} | peers : {}".format(ts, self.session.info.peers_zid()))

            self.process_globals()

            time.sleep(1.0)
        

if __name__ == "__main__":
    with ZvezClockNode(zenoh.KeyExpr(UTILITY_KEY)) as mc:
        mc.spin()