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
            for response in session.get("**"):
                response = response.ok
                print(f"{response.key_expr} => {response.payload.to_string()}")
                
                
if __name__ == "__main__":
    tname = "test" #dt.datetime.now().strftime("HH:MM:SS")
    sc = signal_consumer("generators",tname)
    sc.loop()
