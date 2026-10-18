import zenoh
import random
import numpy
import datetime as dt
import struct
import time

class signal_generator():

    def __init__(self, domain:str, name:str) -> None:
        self.key = "/".join((domain,name))
        self.last_time = dt.datetime.now()
        self.state = numpy.array([1.0,0.0])
        self.A = numpy.array([[0, 1],[-0.2, -0.001]])


    def loop(self):
        with zenoh.open(zenoh.Config()) as session:

            while True:
                t_step = (self.last_time - dt.datetime.now()).total_seconds()
                self.last_time = dt.datetime.now()
                self.state += (self.state @ self.A) * float(t_step)

                session.put(self.key, struct.pack("f",self.state[0]))
                print(self.state[0])

                time.sleep(0.1)
                




if __name__ == "__main__":
    tname = "test" #dt.datetime.now().strftime("HH:MM:SS")
    sg = signal_generator("generators",tname)
    sg.loop()
