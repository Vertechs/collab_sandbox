import json
import logging
import time
import threading
import zenoh
import random
import numpy as np
import datetime as dt
import struct
import time
import logging

from scipy.signal import cont2discrete

import collab_on_zenoh.zvez_global_channels as gc
from collab_on_zenoh.zvez_node import *
from collab_on_zenoh.zvez_weaver import *

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",)
log = logging.getLogger(__name__)

class ZvezTestPlant(ZvezNode):
    def __init__(self,domain: zenoh.KeyExpr, A, B, C, D, dt, x0=None):
        super().__init__()

        self.parent_key = domain

        self.register_producer(self.parent_key.join("state"))
        self.register_producer(self.parent_key.join("output"))

        self.register_consumer(self.parent_key.join("input"), None)

        A, B, C, D = (np.asarray(m, dtype=float) for m in (A, B, C, D))
        discrete_system = cont2discrete((A, B, C, D), dt, method="zoh")
        Ad, Bd, Cd, Dd = (np.asarray(m, dtype=float) for m in discrete_system[:4])
        self.Ad, self.Bd, self.Cd, self.Dd = Ad, Bd, Cd, Dd
        self.x = np.zeros((Ad.shape[0], 1)) if x0 is None else np.array(x0, float).reshape(-1, 1)
        self.u = np.array([[0.0]], float) # TODO get correct shape for B
        self.y = (self.Cd @ self.x + self.Dd @ self.u).item()

        print("shape of state: {}".format(self.x.shape))
        print(list(self.x))

    def spin(self):

        while not self._stop.is_set():
            self.send_sample_now(self.parent_key.join("state"), np.asarray(self.x, dtype="<f4").tobytes())
            self.send_sample_now(self.parent_key.join("output"), np.asarray([self.y], dtype="<f4").tobytes())

            input = self.read_sample_now(self.parent_key.join("input"))
                
            if input:
                self.u = np.array([[struct.unpack('<f', input.to_bytes())[0]]], float)

            print("State: {} | peers : {}".format(list(self.x.flatten()), self.session.info.peers_zid()))

            self.process_globals()

            self.step(self.u)

            time.sleep(1.0)


    def step(self,u):
        u = np.array([[u]], float)
        y = (self.Cd @ self.x + self.Dd @ u).item()
        self.x = self.Ad @ self.x + self.Bd @ u
        self.y = y
        return y

def mass_spring_damper(m=1.0, c=0.8, k=4.0):
    A = [[0.0, 1.0], [-k / m, -c / m]]
    B = [[0.0], [1.0 / m]]
    C = [[1.0, 0.0]]
    D = [[0.0]]
    return A, B, C, D


if __name__ == "__main__":
    A, B, C, D = mass_spring_damper()
    with ZvezTestPlant(zenoh.KeyExpr("@zvez/plant"), A, B, C, D, 1.0) as plant:
        plant.spin()