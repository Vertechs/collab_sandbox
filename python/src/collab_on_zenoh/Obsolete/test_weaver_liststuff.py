import threading
from turtle import listen
import zenoh
import random
import numpy
import datetime as dt
import struct
import time

import collab_on_zenoh.zvez_modules.zvez_global_channels as gc
from collab_on_zenoh.zvez_modules.zvez_node import *
from collab_on_zenoh.zvez_modules.zvez_weaver import *

ROOT_KEY = "@zvez"

class ZvezListStuff(ZvezWeaver):
    def __init__(self, domain: zenoh.KeyExpr):
        super().__init__()

        self.parent_key = domain

        self.plant_web = ZvezWeb(uuid.uuid4())

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

    def add_link_to_web(self, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr):
        edge = self.plant_web.create_new_edge(consumer_key, producer_key)
        if edge is None:
            log.log(logging.ERROR, "Failed to create new edge, max edges reached")
            return False

        self.global_channels.send_link_request(self.plant_web.web_id, edge.edge_id, consumer_key, producer_key)
        return True

    def link_plant(self):
        
        consumer_keys, producer_keys = self.get_all_keys(5.0)

        input_key = None
        output_key = None

        for key in consumer_keys:
            if "input" in key and "plant" in key:
                print("Found plant input key: {}".format(key))
                input_key = zenoh.KeyExpr(key)

        for key in producer_keys:
            if "output" in key and "command" in key:
                print("Found operator command key: {}".format(key))
                output_key = zenoh.KeyExpr(key)

        if input_key is not None and output_key is not None:
            log.log(logging.INFO, "Linking plant input key {} to operator output key {}".format(input_key, output_key))
            self.add_link_to_web(input_key, output_key)
       
    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        

if __name__ == "__main__":
    with ZvezListStuff(zenoh.KeyExpr(ROOT_KEY)) as lister:
        while 1:
            print(lister.get_all_keys(3.0))
            print(lister.session.info.peers_zid())
            time.sleep(5.0)