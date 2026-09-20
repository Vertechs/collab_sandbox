import zenoh
import random
import numpy
import datetime as dt
import struct
import time

class signal_consumer():

    def __init__(self, domain:str, name:str) -> None:
        self.key = "/".join((domain,name))
        self.history = []


    def loop(self):
        with zenoh.open(zenoh.Config()) as session:
            for resp in session.get("generators/**"):
                resp = resp.ok
            with session.declare_subscriber(self.key) as subsc:
                for sample in subsc:
                    val = struct.unpack("f",sample.payload.to_bytes())
                    print(f"At {sample.timestamp}, {sample.key_expr} said {sample.payload.to_bytes().hex()} means {val}")
                
                
if __name__ == "__main__":
    tname = "test" #dt.datetime.now().strftime("HH:MM:SS")
    sc = signal_consumer("generators",tname)
    sc.loop()
