import threading
from turtle import listen
import zenoh
import random
import numpy
import datetime as dt
import struct
import time

import collab_on_zenoh.zvez_global_channels as gc
from collab_on_zenoh.zvez_node import *
from collab_on_zenoh.zvez_weaver import *

UTILITY_KEY = "@zvez/util"

class ZvezListStuff(ZvezWeaver):
    def __init__(self, domain: zenoh.KeyExpr):
        super().__init__()

        self.parent_key = domain.join("clock")

    def get_all_keys(self, listening_time: float):
        self.global_channels.send_echo_request(self.parent_key.join("**"), "A")

        start_read = dt.datetime.now(dt.timezone.utc).timestamp()

        consumer_keys = set()
        producer_keys = set()
        while (dt.datetime.now(dt.timezone.utc).timestamp() - start_read) < (listening_time):
            consumer = self.global_channels.read_consumer()
            if consumer: consumer_keys.add(consumer)
            producer = self.global_channels.read_producer()
            if producer: producer_keys.add(producer)

        return consumer_keys,producer_keys



    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        

if __name__ == "__main__":
    with ZvezListStuff(zenoh.KeyExpr(UTILITY_KEY)) as lister:
        while 1:
            print(lister.get_all_keys(3.0))
            time.sleep(5.0)