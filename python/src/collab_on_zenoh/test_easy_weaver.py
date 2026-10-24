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
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",)
log = logging.getLogger(__name__)

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
            time.sleep(0.1)

        return consumer_keys,producer_keys

    def add_link_to_web(self, consumer_key: zenoh.KeyExpr, producer_key: zenoh.KeyExpr):
        edge = self.plant_web.create_new_edge(consumer_key, producer_key)
        if edge is None:
            log.log(logging.ERROR, "Failed to create new edge, max edges reached")
            return False

        self.global_channels.send_link_request(self.plant_web.web_id, edge.edge_id, consumer_key, producer_key)
        return True

    def get_all_responses(self):
        responses = []
        while True:
            response = self.global_channels.read_response()
            if not response:
                break
            responses.append(response)
        return responses

    def link_raw_keys(self, consumer_key:str, producer_key:str):
        pass
        
       
    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        

if __name__ == "__main__":
    with ZvezListStuff(zenoh.KeyExpr(ROOT_KEY)) as lister:
        while 1:
            instr = input('>').replace(',', ' ').split(' ')
            first = instr[0]
            match first:
                case "list":
                    waittime = float(instr[1]) if len(instr) > 1 else 3.0
                    print("Consumers:\n{}\nProducers:\n{}".format(*lister.get_all_keys(waittime)))
                case "peers":
                    print("Peers:\n{}".format(lister.session.info.peers_zid()))
                case "link":
                    try:
                        key1 = zenoh.KeyExpr(instr[1])
                        key2 = zenoh.KeyExpr(instr[2])
                        lister.add_link_to_web(key1, key2)
                    except Exception as e:
                        print(f"Error: {e}")
                case "linkrand":
                    import random
                    consumer_keys, producer_keys = lister.get_all_keys(3.0)
                    if consumer_keys and producer_keys:
                        consumer_key = random.choice(list(consumer_keys))
                        producer_key = random.choice(list(producer_keys))
                        while consumer_key.split('/')[-2] == producer_key.split('/')[-2]:
                            producer_key = random.choice(list(producer_keys))
                        lister.add_link_to_web(consumer_key, producer_key)
                case 'check':
                    print("repsonses: {}".format(lister.get_all_responses()))
                case _:
                    print("Unknown command {}".format(first.encode()))

# link,@zvez/consensus/21/neighbor_states,@zvez/consensus/96/state