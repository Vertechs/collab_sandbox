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

from scipy.signal import cont2discrete

import collab_on_zenoh.zvez_modules.zvez_global_channels as gc
from collab_on_zenoh.zvez_modules.zvez_node import *
from collab_on_zenoh.zvez_modules.zvez_weaver import *

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",)
log = logging.getLogger(__name__)

class ZvezOperator(ZvezNode):
    def __init__(self,domain: zenoh.KeyExpr):
        super().__init__()

        self.parent_key = domain

        self.register_producer(self.parent_key.join("command"))

        self.register_consumer(self.parent_key.join("command_fb"), None)

        self.command_queue: queue.Queue[str] = queue.Queue()

    def _input_thread(self):
        while not self._stop.is_set():
            command = input("Enter command:")
            if command:
                self.command_queue.put(command)

    def spin(self):
        threading.Thread(target=self._input_thread, daemon=True).start()

        while not self._stop.is_set():
            self.process_globals()
            
            try:
                command = self.command_queue.get_nowait()
                log.log(logging.INFO, "Sending command: {}".format(command))
                self.send_sample_now(self.parent_key.join("command"), command.encode('utf-8'))

            except queue.Empty:
                pass

            time.sleep(1.0)






if __name__ == "__main__":
    with ZvezOperator(zenoh.KeyExpr("@zvez/operator")) as operator:
        operator.spin()