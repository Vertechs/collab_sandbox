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
        conf = zenoh.Config()
        conf.insert_json5("listen/endpoints", '["tcp/10.0.0.33:7447"]')
        with zenoh.open(conf) as session:
            with session.declare_subscriber(self.key) as subsc:
                for sample in subsc:
                    val = "null"#struct.unpack("f",sample.payload.to_bytes())
                    print(f"At {sample.timestamp}, {sample.key_expr} said {sample.payload}")
                
                
if __name__ == "__main__":
    tname = "test" #dt.datetime.now().strftime("HH:MM:SS")
    sc = signal_consumer("esp_test","temp1")
    sc.loop()
