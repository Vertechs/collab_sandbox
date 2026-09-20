import socket
import time
import configparser
import logging

config = configparser.ConfigParser()
config.read("config.ini")

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class weaver_node:
    def __init__(self) -> None:
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.logger = logging.getLogger(__name__+"weaver")

    def start_listening(self):
        self.listener_socket.bind((config["addr_waver_listen"], config["port_general_to_weaver"]))
        self.logger.info(f"listening on {config['addr_waver_listen']}:{config['port_general_to_weaver']}")

    def reach_out(self):
        message = 0 #TODO
        self.broadcast_socket.sendto(message,'<broadcast>')


    def scan(self):
        resp_data, resp_addr = self.listener_socket.recvfrom(1024)
