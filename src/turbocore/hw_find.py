import re
import socket
import argparse

HOSTNAME = socket.gethostname()


def get_cpu_serial_number():
    with open("/proc/cpuinfo") as f_cpu_info:
        serials = [
            match.group(1)
            for i in f_cpu_info.readlines()
            for match in [re.search(r'Serial\s+:\s*(\w+)', i)]
            if match
        ]
    if len(serials) == 1:
        return serials[0].upper()


class LOBOTListener:
    def __init__(self, robot_type, address, port):
        self.robot_type = robot_type
        self.address = address
        self.port = port
        self.ident = f"{self.robot_type}:{get_cpu_serial_number():0<32}"
        self.udp_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_server.bind((self.address, self.port))

    def send(self, msg):
        self.udp_server.sendto(bytes(msg + '\n', encoding='utf-8'), (self.address, self.port))

    def recv(self):
        data, _addr = self.udp_server.recvfrom(1024)
        msg = str(data, encoding='utf-8')
        if msg == "LOBOT_NET_DISCOVER":
            self.send(self.ident)
        elif msg == "LOBOT_NET_DISCOVER_HOSTNAME":
            self.send(self.ident + f":{HOSTNAME}")

    def loop(self):
        while True:
            self.recv()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--robot_type', default='TurboPi', help='robot type')
    parser.add_argument('-a', '--address', default='0.0.0.0', help='address to bind to')
    parser.add_argument('-p', '--port', default=9027, help='port to bind to')
    args = parser.parse_args()
    udp_listener = LOBOTListener(args.robot_type, args.address, args.port)
    udp_listener.loop()
