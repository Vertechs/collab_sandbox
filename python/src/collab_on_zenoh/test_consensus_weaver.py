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


class ZvezConsWeaver():
    def __init__(self):
        self.zvez_weaver = ZvezWeaver()
        self.zvez_weaver.__init__()

    def spin(self):

        with self.zvez_weaver:
          while True:
            time.sleep(1)






if __name__ == "__main__":
    consensus_weaver = ZvezConsWeaver()
    consensus_weaver.spin()