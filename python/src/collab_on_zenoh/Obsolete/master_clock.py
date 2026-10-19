import threading
import zenoh
import random
import numpy
import datetime as dt
import struct
import time

import collab_on_zenoh.zvez_global_channels as gc
from collab_on_zenoh.zvez_node import *


CLOCK_KEYS = {'now_s': 'time', 'now_ms': 'time_ms'}
UTILITY_KEY = "@zvez/util/"


class ZvezClockNode(ZvezNode):
    def __init__(self, domain: str):
        super().__init__()

        self.parent_key = zenoh.KeyExpr("/".join((domain,"clock")))

        self.register_producer(self.parent_key.join("time_s"))
        self.register_producer(self.parent_key.join("time_ms"))

    def spin(self):
        ts = dt.datetime.now(dt.timezone.utc).timestamp()

        self.send_sample_now(self.parent_key.join("time_s"), struct.pack('<I', int(ts)))
        self.send_sample_now(self.parent_key.join("time_ms"), struct.pack('<I', int(ts%1.0 * 1000)))

        print("Time: {} | peers : {}".format(ts, self.session.info.peers_zid()))
        


class ZvezStandaloneMasterClock():

    def __init__(self, domain:str) -> None:
        self.parent_key = "/".join((domain,"clock"))
        self.update_period = 1.0

        self._stop = threading.Event()
        self._match = threading.Event()

        self.session = zenoh.open(zenoh.Config())
        self.global_channels = gc.ZvezNodeGlobalChannels(self.session)

        self.publishers = {key : self.session.declare_publisher(self.parent_key+'/'+CLOCK_KEYS[key]) for key in CLOCK_KEYS}

        self.data_dict = dict.fromkeys(CLOCK_KEYS, 0)
        self.format_dict = {key : '<I' for key in CLOCK_KEYS}

    def get_keys(self):
        return [zenoh.KeyExpr(self.parent_key+"/"+key) for key in self.publishers]
    
    def _update_data(self):
        ts = dt.datetime.now(dt.timezone.utc).timestamp()
        self.data_dict['now_s'] = int(ts)
        self.data_dict['now_ms'] = int(ts%1.0 * 1000)

    def global_callback(self, request):
        if request['type'] == 'echo':
            self.global_channels.list_produced_keys(self.get_keys())
        elif request['type'] == 'link':
            if request['producer_key'] in self.get_keys():
                self.global_channels.send_response('LINK', request['webID'], request['edgeID'], 'FAIL')

    def spin(self):

        while not self._stop.is_set():
            self._update_data()
            for key in self.publishers:
                try:
                    self.publishers[key].put(struct.pack(self.format_dict[key], self.data_dict[key]))
                except Exception as e:
                    print(f"Error occurred while updating publisher for key {key}: {e}")

            print("Time: {} | peers : {}".format(self.data_dict['now_s'], self.session.info.peers_zid()))

            self._stop.wait(self.update_period) #todo: cycle time not between-task time


    def close(self):
        self._stop.set()
        for publisher in self.publishers.values():
            publisher.undeclare()
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()




if __name__ == "__main__":
    # with ZvezStandaloneMasterClock(CLOCK_KEY) as mc:
    #     mc.spin()
    with ZvezClockNode(UTILITY_KEY) as mc:
        mc.spin()