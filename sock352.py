"""
NAME: DHRUVIL PATEL <dhp68 | 171004047> & KABIR KURIYAN <kjk174 | 169005863>
GROUP # 18
PROJECT: CS352 -- PART 2
"""
import binascii
import time
from math import ceil

import socket as syssock
import struct
import threading
import sys
import random

# these functions are global to the class and define the UDP ports all messages are sent and received from

# Usage:
# server2.py -f shakespeare.txt -u 8888 -v 9999
# client2.py -d localhost -f loremipsum.txt -u 9999 -v 8888

version = 0x1
sock352PktHdrData = "!BBBBHHLLQQLL"
PACKET_HEADER_LENGTH = struct.calcsize(sock352PktHdrData)
UDPPKT_HDR_DATA = struct.Struct(sock352PktHdrData)

MAXIMUM_PACKET_SIZE = 4096
MAXIMUM_PAYLOAD_SIZE = MAXIMUM_PACKET_SIZE - PACKET_HEADER_LENGTH
MAX_WINDOW = 64000

SOCK352_SYN = 0x01
SOCK352_FIN = 0x02
SOCK352_ACK = 0x04
SOCK352_RESET = 0x08
SOCK352_HAS_OPT = 0x10

PACKET_FLAG_INDEX = 1
PACKET_SEQUENCE_NO_INDEX = 8
PACKET_ACK_NO_INDEX = 9
WINDOW_INDEX = 10

UDPTx = 27182
UDPRx = 27182


def init(UDPportTx, UDPportRx):  # initialize your UDP socket here
    global UDPRx, UDPTx
    UDPTx = UDPportTx
    UDPRx = UDPportRx


class socket:

    def __init__(self):  # fill in your code here
        self.socket = syssock.socket(syssock.AF_INET, syssock.SOCK_DGRAM)
        self.socket.settimeout(0.2)
        self.seq_no = random.randint(1, 100000)
        self.data_packets = []
        self.ack_no = 0
        self.rn = 0
        self.my_rn = 0
        self.lock = threading.Lock()
        self.done = False
        self.timeout = False
        self.is_connected = False
        self.send_address = None
        self.recv_address = None
        self.more_to_send = 0
        self.recv_window = MAX_WINDOW
        self.more_send_buffer = 0
        self.buffer_size = 14556
        return

    def bind(self, address):
        self.socket.bind((address[0], int(UDPRx)))
        return

    def connect(self, address):  # fill in your code here
        syn_ack_packet = None
        self.send_address = (address[0], int(UDPTx))
        print("Send address is: ", self.send_address)
        self.socket.bind((address[0], int(UDPRx)))
        if self.is_connected:
            print("Connection is already established!!!")
            return

        synPacket = self.createPacket(SOCK352_SYN, sequence_no=self.seq_no)
        self.socket.sendto(synPacket, self.send_address)
        self.seq_no += 1
        received_handshake_packet = False
        while not received_handshake_packet:
            try:
                (syn_ack_packet, addr) = self.socket.recvfrom(PACKET_HEADER_LENGTH)
                syn_ack_packet = UDPPKT_HDR_DATA.unpack(syn_ack_packet)
                if syn_ack_packet[PACKET_FLAG_INDEX] == SOCK352_RESET:
                    print("Connection reset by the server!!!")
                    return
                if syn_ack_packet[PACKET_FLAG_INDEX] == SOCK352_SYN | SOCK352_ACK:
                    received_handshake_packet = True
                if syn_ack_packet[PACKET_ACK_NO_INDEX] != self.seq_no:
                    received_handshake_packet = False
            except syssock.timeout:
                self.socket.sendto(synPacket, self.send_address)

        self.ack_no = syn_ack_packet[PACKET_SEQUENCE_NO_INDEX] + 1
        ackPacket = self.createPacket(flags=SOCK352_ACK,
                                      sequence_no=self.seq_no,
                                      ack_no=self.ack_no)
        self.seq_no += 1
        self.is_connected = True
        self.socket.sendto(ackPacket, self.send_address)
        print("Client is connected to the server at %s:%s" % (self.send_address[0], self.send_address[1]))

    def listen(self, backlog):
        return

    def accept(self):
        # print("in accept")
        global ack_packet, syn_packet, addr
        if self.is_connected:
            print("Error: Connection is already established!!!")
            return
        got_connection_request = False
        while not got_connection_request:
            try:
                (syn_packet, addr) = self.socket.recvfrom(PACKET_HEADER_LENGTH)
                syn_packet = UDPPKT_HDR_DATA.unpack(syn_packet)
                if syn_packet[PACKET_FLAG_INDEX] == SOCK352_SYN:
                    got_connection_request = True
                if syn_packet[PACKET_FLAG_INDEX] == SOCK352_SYN | SOCK352_HAS_OPT:
                    got_connection_request = True

            except syssock.timeout:
                pass

        flags = SOCK352_SYN | SOCK352_ACK
        syn_ack_packet = self.createPacket(flags=flags,
                                           sequence_no=self.seq_no,
                                           ack_no=syn_packet[PACKET_SEQUENCE_NO_INDEX] + 1)
        self.seq_no += 1
        self.socket.sendto(syn_ack_packet, addr)
        got_final_ack = False
        while not got_final_ack:
            try:
                (ack_packet, addr) = self.socket.recvfrom(PACKET_HEADER_LENGTH)
                ack_packet = UDPPKT_HDR_DATA.unpack(ack_packet)
                if ack_packet[PACKET_FLAG_INDEX] == SOCK352_ACK:
                    got_final_ack = True
            except syssock.timeout:
                self.socket.sendto(syn_ack_packet, addr)
        self.ack_no = ack_packet[PACKET_SEQUENCE_NO_INDEX] + 1
        self.send_address = (addr[0], int(UDPTx))
        self.is_connected = True
        print("Server is now connected to the client at %s:%s\n" % (self.send_address[0], self.send_address[1]))
        return self, addr

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

    def create_data_packets(self, buffer):
        total_packets = int(len(buffer) / MAXIMUM_PAYLOAD_SIZE)
        if len(buffer) % MAXIMUM_PAYLOAD_SIZE != 0:
            total_packets += 1
        payload_len = MAXIMUM_PAYLOAD_SIZE

        for i in range(0, total_packets):
            if i == total_packets - 1:
                if len(buffer) % MAXIMUM_PAYLOAD_SIZE != 0:
                    payload_len = len(buffer) % MAXIMUM_PAYLOAD_SIZE
            new_packet = self.createPacket(flags=0x0,
                                           sequence_no=self.seq_no,
                                           ack_no=self.ack_no,
                                           payload_len=payload_len)
            self.seq_no += 1
            self.ack_no += 1
            self.data_packets.append(new_packet)

        return total_packets

    def send(self, buffer):
        self.socket.settimeout(0.2)
        goal = self.rn + len(buffer)
        total_packets = self.create_data_packets(buffer)
        if total_packets > 1:
            print("Total packets: " + str(total_packets))

        ack_thread = threading.Thread(target=self.recv_acks, args=(goal,))
        num_left = len(buffer)
        start_rn = imagined_rn = self.rn
        ack_thread.start()
        if total_packets > 1:
            print("-------Started data packet transmission...-------")
        while ack_thread.isAlive():
            with self.lock:
                if self.timeout:
                    imagined_rn = self.rn
                    self.timeout = False
                if imagined_rn >= goal:
                    imagined_rn = max(imagined_rn - MAXIMUM_PAYLOAD_SIZE, start_rn)
                start_index = imagined_rn - start_rn
                num_left = goal - imagined_rn
                end_index = start_index + min(num_left, MAXIMUM_PAYLOAD_SIZE)
                payload = buffer[start_index: end_index]
                if imagined_rn > 0:
                    print(f"In send(), sending seq {imagined_rn} from {start_index} to {end_index}, with {num_left} left")
                self.send_packet(seq_no=imagined_rn, payload=payload)
                imagined_rn += len(payload)
        if total_packets > 1:
            print("-------Finished transmitting data packets-------")
        return len(buffer)

    def recv(self, nbytes):
        good_packet_list = []
        self.socket.settimeout(None)
        goal_length = int(ceil(float(nbytes) / MAXIMUM_PAYLOAD_SIZE))
        if self.more_to_send < 0:
            self.recv_window = MAX_WINDOW
        self.more_to_send = self.recv_window - 40
        self.recv_window = self.more_to_send
        if self.more_send_buffer < 0:
            self.buffer_size = MAXIMUM_PACKET_SIZE
            print('-----Oops, the buffer is full!-----')
        self.more_send_buffer = self.buffer_size - 40
        self.buffer_size = self.more_send_buffer
        print("# of bytes left in buffer: " + str(self.more_send_buffer))
        print("After receiving packet, the window: " + str(self.more_to_send))
        while len(good_packet_list) < goal_length:
            if len(good_packet_list) == goal_length:
                num_to_get = PACKET_HEADER_LENGTH + nbytes - ((goal_length - 1) * MAXIMUM_PAYLOAD_SIZE)
            else:
                num_to_get = PACKET_HEADER_LENGTH + MAXIMUM_PAYLOAD_SIZE
            data_pack = self.get_packet(size=num_to_get)
            if data_pack['flags'] != 0:
                print('Probably getting extra from handshake', data_pack['flags'])
            elif data_pack['seq_no'] == self.my_rn:
                self.my_rn += data_pack['payload_len']
                good_packet_list.append(data_pack['payload'])
            self.send_packet(ack_no=self.my_rn, flags=SOCK352_ACK)
            # print(f"In recv(), receiving seq {self.my_rn}")

        final_string = b''.join(good_packet_list)
        return final_string

    def register_timeout(self):
        with self.lock:
            self.timeout = True

    def recv_acks(self, goal_rn):
        timer = time.time()
        while self.rn < goal_rn:
            ack_pack = self.get_packet()
            self.timeout = True
            if ack_pack['flags'] == SOCK352_ACK:
                if ack_pack['ack_no'] > self.rn:
                    with self.lock:
                        self.rn = ack_pack['ack_no']
                    timer = time.time()
                elif ack_pack['flags'] == SOCK352_RESET:
                    self.send_packet(ack_no=self.rn, flags=SOCK352_ACK)
                    return
                if time.time() - timer > 0.2:
                    self.register_timeout()

    def doNothing(self):
        pass

    def get_packet(self, size=PACKET_HEADER_LENGTH):
        global header_values
        try:
            packet, addr = self.socket.recvfrom(size)
        except syssock.timeout:
            return dict(zip(('version', 'flags', 'opt_ptr', 'protocol', 'checksum', 'header_len', 'source_port',
                             'dest_port', 'seq_no', 'ack_no', 'window', 'payload_len', 'payload', 'address'),
                            (-1 for i in range(14))))
        header = packet[:PACKET_HEADER_LENGTH]
        header_values = UDPPKT_HDR_DATA.unpack(header)
        if len(packet) > PACKET_HEADER_LENGTH:
            payload = packet[PACKET_HEADER_LENGTH:]
        else:
            payload = 0
        return_values = header_values + (payload, addr)
        return_dict = dict(zip(('version', 'flags', 'opt_ptr', 'protocol', 'checksum', 'header_len', 'source_port',
                                'dest_port', 'seq_no', 'ack_no', 'window', 'payload_len', 'payload', 'address'),
                               return_values))
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
        header_len = PACKET_HEADER_LENGTH
        header = UDPPKT_HDR_DATA.pack(version, flags, opt_ptr, protocol, checksum, header_len,
                                      source_port, dest_port, seq_no, ack_no, window, payload_len)
        packet = header + payload
        # print(f"Package sending is seq {seq_no} with ack {ack_no} ")
        self.socket.sendto(packet, dest)
        return packet

    def createPacket(self, flags=0x0, sequence_no=0x0, ack_no=0x0, payload_len=0x0, window=0x0):
        return UDPPKT_HDR_DATA.pack(0x1, flags, 0x0, 0x0, PACKET_HEADER_LENGTH,
                                    0x0, 0x0, 0x0, sequence_no, ack_no, window, payload_len)

