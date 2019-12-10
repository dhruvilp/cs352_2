import binascii
import time
from math import ceil

import socket as syssock
import struct
import threading
import sys
import random

SOCK352_SYN = 0x01
SOCK352_FIN = 0x02
SOCK352_ACK = 0x04
SOCK352_RESET = 0x08
SOCK352_HAS_OPT = 0xA0
MAX_PAYLOAD_SIZE = 64000
HEADER_LEN = 40
HEADER_SIZE = MAX_PAYLOAD_SIZE + HEADER_LEN

send_port = 0
recv_port = 0


def init(UDPportTx, UDPportRx):  # initialize your UDP socket here
    global send_port, recv_port
    send_port = UDPportTx
    recv_port = UDPportRx


class socket:

    def __init__(self):  # fill in your code here
        sock352PktHdrData = '!BBBBHHLLQQLL'
        self.struct = struct.Struct(sock352PktHdrData)
        self.socket = syssock.socket(syssock.AF_INET, syssock.SOCK_DGRAM)
        self.rn = 0
        self.my_rn = 0
        self.done = False
        self.lock = threading.Lock()
        self.timeout = False
        return

    def bind(self, address):
        global recv_port
        self.recv_address = (address[0], int(recv_port))
        self.socket.bind(self.recv_address)
        return

    def connect(self, address):  # fill in your code here
        print("calling connect")
        global send_port, recv_port
        self.recv_address = (syssock.gethostname(), int(recv_port))
        self.socket.bind(self.recv_address)
        self.send_address = (str(address[0]), int(send_port))
        self.socket.settimeout(0.2)
        done = False
        self.rn = random.randint(1, 1000)
        while not done:
            self.send_packet(seq_no=self.rn, flags=SOCK352_SYN)
            syn_ack = self.get_packet()
            if syn_ack['flags'] == SOCK352_SYN | SOCK352_ACK:
                done = True
                self.my_rn = syn_ack['seq_no'] + 1
                self.rn = syn_ack['ack_no']
                self.send_packet(ack_no=self.my_rn, flags=SOCK352_ACK)
        print("Connection established")
        
        return

    def listen(self, backlog):
        return

    def accept(self):
        print("in accept")
        global send_port
        done = False
        while not done:
            print("waiting for first packet")
            first_packet = self.get_packet()
            if first_packet['flags'] == SOCK352_SYN:
                done = True
                self.my_rn = first_packet['seq_no'] + 1
            else:
                self.send_packet(dest=first_packet['address'], ack_no=self.my_rn, flags=SOCK352_RESET)
        self.socket.settimeout(0.2)
        self.send_address = (first_packet['address'][0], int(send_port))
        done = False
        self.rn = random.randint(1, 1000)
        while not done:
            self.send_packet(seq_no=self.rn, ack_no=self.my_rn, flags=SOCK352_SYN | SOCK352_ACK)
            second_packet = self.get_packet()
            if second_packet['flags'] == SOCK352_ACK and second_packet['ack_no'] == self.rn + 1:
                self.rn = second_packet['ack_no']
                done = True
            else:
                self.send_packet(ack_no=self.rn, flags=SOCK352_RESET)
        print("Connection established")
        return (self, self.send_address)

    def close(self):  # fill in your code here
        self.socket.settimeout(0.2)
        fin_sent = False
        while not self.done or not fin_sent:
            self.send_packet(seq_no=self.my_rn, flags=SOCK352_FIN)
            fin_pack = self.get_packet()
            if fin_pack['flags'] == SOCK352_FIN:
                self.send_packet(ack_no=fin_pack['seq_no'] + 1, flags=SOCK352_ACK)
                self.done = True
            elif fin_pack['flags'] == SOCK352_ACK and fin_pack['ack_no'] == self.my_rn + 1:
                fin_sent = True
        self.socket.settimeout(1)
        timeout = 0
        while True:
            fin_pack = self.get_packet()
            timeout = fin_pack['payload_len']
            if timeout == -1:
                return
            else:
                if fin_pack['flags'] == SOCK352_FIN:
                    self.send_packet(ack_no=fin_pack['seq_no'] + 1, flags=SOCK352_ACK)

    def send(self, buffer):
        self.socket.settimeout(0.2)
        goal = self.rn + len(buffer)
        ack_thread = threading.Thread(target=self.recv_acks, args=(goal,))
        num_left = len(buffer)
        start_rn = self.rn
        imagined_rn = self.rn
        ack_thread.start()
        while ack_thread.isAlive():
            with self.lock:
                if self.timeout:
                    imagined_rn = self.rn
                    self.timeout = False
                if imagined_rn >= goal:
                    imagined_rn = max(imagined_rn - MAX_PAYLOAD_SIZE, start_rn)
                start_index = imagined_rn - start_rn
                num_left = goal - imagined_rn
                end_index = start_index + min(num_left, MAX_PAYLOAD_SIZE)
                payload = buffer[start_index : end_index]
                print(f"In send(), sending seq {imagined_rn} from {start_index} to {end_index}, with {num_left} left")
                self.send_packet(seq_no=imagined_rn, payload=payload)
                imagined_rn += len(payload)
        print("leaving send()")
        return len(buffer)

    def recv(self, nbytes):
        good_packet_list = []
        self.socket.settimeout(None)
        goal_length = int(ceil(float(nbytes) / MAX_PAYLOAD_SIZE))
        while len(good_packet_list) < goal_length:
            x = len(good_packet_list)
            
            if len(good_packet_list) == goal_length -1:
                num_to_get = HEADER_LEN + nbytes - ((goal_length - 1) * MAX_PAYLOAD_SIZE)
            else:
                num_to_get = HEADER_LEN + MAX_PAYLOAD_SIZE
            print(f"Goal is {goal_length} currently at {x}, leaving {num_to_get}")
            data_pack = self.get_packet(size=num_to_get)
            if(data_pack['flags'] != 0):
                print('Probably getting extra from handshake', data_pack['flags'])
                if data_pack['flags'] == SOCK352_FIN:
                    #self.done = True
                    #self.send_packet(ack_no=data_pack['seq_no'] + 1, flags=SOCK352_ACK)
                    print("Fin flag sent")
                    print(good_packet_list)
                    final_string = b''.join(good_packet_list)

                    return final_string
                    break
            elif data_pack['seq_no'] == self.my_rn:
                self.my_rn += data_pack['payload_len']
                good_packet_list.append(data_pack['payload'])
            self.send_packet(ack_no = self.my_rn, flags=SOCK352_ACK)

        print(good_packet_list)
        final_string = b''.join(good_packet_list)

        return final_string

    def register_timeout(self):
        with self.lock:
            self.timeout = True

    def recv_acks(self, goal_rn):
        timer = time.time()
        while self.rn < goal_rn:
            ack_pack = self.get_packet(timeout_func=self.register_timeout)
            if ack_pack['flags'] == SOCK352_ACK:
                if ack_pack['ack_no'] > self.rn:
                    with self.lock:
                        self.rn = ack_pack['ack_no']
                    timer = time.time()
                elif ack_pack['flags'] == SOCK352_RESET:
                    self.send_packet(ack_no=self.rn, flags=SOCK352_ACK)
                elif ack_pack['flags'] == SOCK352_FIN:
                    self.done = True
                    self.send_packet(ack_no=ack_pack['seq_no'] + 1, flags=SOCK352_ACK)
                    return
                if time.time() - timer > 0.2:
                    self.register_timeout()

    def doNothing():
        pass

    def get_packet(self, size=HEADER_LEN, timeout_func=doNothing):
        try:
            packet, addr = self.socket.recvfrom(size)
        except syssock.timeout:
            timeout_func()
            return dict(zip(('version', 'flags', 'opt_ptr', 'protocol', 'checksum', 'header_len', 'source_port', 'dest_port', 'seq_no', 'ack_no', 'window', 'payload_len', 'payload', 'address'), (-1 for i in range(14))))
        header = packet[:HEADER_LEN]
        header_values = self.struct.unpack(header)
        if len(packet) > HEADER_LEN:
            payload = packet[HEADER_LEN:]
        else:
            payload = 0
        return_values = header_values + (payload, addr)
        return_dict = dict(zip(('version', 'flags', 'opt_ptr', 'protocol', 'checksum', 'header_len', 'source_port', 'dest_port', 'seq_no', 'ack_no', 'window', 'payload_len', 'payload', 'address'), return_values))
        return return_dict

    def send_packet(self, dest=None, seq_no=0, ack_no=0, payload=b'', flags=0):
        if dest is None:
            dest = self.send_address
        version = 1
        opt_ptr = 0
        protocol = 0
        checksum = 0
        source_port = 0
        dest_port = 0
        window = 0
        payload_len = len(payload)
        header_len = HEADER_LEN
        header = self.struct.pack(version, flags, opt_ptr, protocol, checksum, header_len,
                                  source_port, dest_port, seq_no, ack_no, window, payload_len)
        packet = header + payload
        print(f"Package sending is seq {seq_no} with ack {ack_no} ")
        self.socket.sendto(packet, dest)



