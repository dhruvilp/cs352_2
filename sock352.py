"""
NAME: DHRUVIL PATEL <dhp68 | 171004047> & KABIR KURIYAN <kjk174 | 169005863>
GROUP # 18
PROJECT: CS352 -- PART 2
"""

import binascii
import ta_sockets as syssock
import struct
import sys
import time
import threading
import random

# these functions are global to the class and define the UDP ports all messages are sent and received from

# Usage:
# server1.py -f test.txt -u 8888 -v 9999
# client1.py -d localhost -f test.txt -u 9999 -v 8888

SOCK352_SYN = 0x01
SOCK352_FIN = 0x02
SOCK352_ACK = 0x04
SOCK352_RESET = 0x08
SOCK352_HAS_OPT = 0xA0

version = 0x1
sock352PktHdrData = '!BBBBHHLLQQLL'
header_len = struct.calcsize(sock352PktHdrData)
udpPkt_hdr_data = struct.Struct(sock352PktHdrData)

MAXIMUM_PACKET_SIZE = 64000
MAXIMUM_PAYLOAD_SIZE = MAXIMUM_PACKET_SIZE - header_len

PACKET_FLAG_INDEX = 1
PACKET_SEQUENCE_NO_INDEX = 8
PACKET_ACK_NO_INDEX = 9
PACKET_DEST_PORT = 7
PACKET_PAYLOAD_LEN = 11
FLAG_RESET = -1

UDPTx = 27182  # transmitter port
UDPRx = 27182  # receiver port


def init(UDPportTx, UDPportRx):  # initialize your UDP socket here
    global UDPRx, UDPTx
    UDPTx = UDPportTx
    UDPRx = UDPportRx

class socket:
    def __init__(self):  # fill in your code here
        self.address = ('', int(UDPRx))
        self.struct = struct.Struct(sock352PktHdrData)
        self.socket = syssock.socket(syssock.AF_INET, syssock.SOCK_DGRAM)
        self.acknowledge_no = 0
        self.sequence_no = 0
        self.client_no = 0
        self.connection = False
        self.server_address = None
        self.go_back_n = False
        self.fragment_size = 8192  # 64K bytes
        self.is_server_established = False
        self.data_packets = []
        self.lock = threading.Lock()

        return

    def bind(self, address):
        return

    def create_packet(self, dest=None, seq_no=0, ack_no=0, payload=b'', flags=0):
        if dest is None:
            dest = self.server_address
        version = 1
        opt_ptr = 1
        protocol = 0
        checksum = 0
        source_port = 0
        dest_port = 0
        window = 0
        payload_len = len(payload)
        header = udpPkt_hdr_data.pack(version, flags, opt_ptr, protocol, checksum, header_len,
                                  source_port, dest_port, seq_no, ack_no, window, payload_len)
        packet = header + payload
        return packet

    def connect(self, address):  # fill in your code here
        print('Connecting. . .')
        self.server_address = address[0]
        self.socket.bind(('', int(UDPRx)))
        self.is_server_established = False
        self.socket.settimeout(0.2)
        print("Sending and receiving sockets have been successfully initialized!")

        self.sequence_no = random.randint(1, 255)
        s_header = self.create_header(SOCK352_SYN, self.sequence_no, 0, 0)
        try:
            self.socket.sendto(s_header, (self.server_address, int(UDPTx)))
            print("Request sent!")
            server_packet = self.socket.recv(header_len)
        except syssock.timeout:
            print("Error: Timed out!")
            return
        if len(server_packet) is not None:
            u_header = udpPkt_hdr_data.unpack(server_packet)
            if SOCK352_SYN == u_header[PACKET_FLAG_INDEX]:
                self.acknowledge_no = u_header[PACKET_ACK_NO_INDEX]
                self.sequence_no = u_header[PACKET_SEQUENCE_NO_INDEX]
            elif SOCK352_RESET == u_header[PACKET_FLAG_INDEX]:
                self.sequence_no += 1
                print('Error: Connection already exists!')
            else:
                sys.exit('Error: Failed to establish the connection!')

        p_header = udpPkt_hdr_data.pack(version, SOCK352_ACK, 0, 0, header_len, 404, 0, 0, self.sequence_no,
                                        self.acknowledge_no, 404, 0)
        self.socket.sendto(p_header, (self.server_address, int(UDPTx)))
        print("Connection successfully established!"),
        return

    def listen(self, backlog):
        return

    def accept(self):  # fill in your code here
        client_packet = None
        client_address = 0
        self.sequence_no = random.randint(1, 18000)
        self.socket.bind(self.address)
        self.is_server_established = True

        while client_packet is None:
            (client_packet, client_address) = self.socket.recvfrom(header_len)

        sock352_flags = FLAG_RESET
        u_header = udpPkt_hdr_data.unpack(client_packet)
        if SOCK352_SYN == u_header[PACKET_FLAG_INDEX] and self.connection is True:
            sock352_flags = SOCK352_RESET
            self.acknowledge_no = u_header[PACKET_DEST_PORT] + 1
        elif SOCK352_SYN == u_header[PACKET_FLAG_INDEX] and self.connection is False:
            sock352_flags = SOCK352_SYN
            self.acknowledge_no = u_header[PACKET_DEST_PORT] + 1

        p_header = udpPkt_hdr_data.pack(version, sock352_flags, 0, 0, header_len, 404, 0, 0, self.sequence_no,
                                        self.acknowledge_no, 404, 0)
        self.socket.sendto(p_header, (client_address[0], int(UDPTx)))
        self.connection = True

        (client_packet, client_address) = self.socket.recvfrom(header_len)
        u_header = udpPkt_hdr_data.unpack(client_packet)
        self.sequence_no = u_header[PACKET_ACK_NO_INDEX]
        self.acknowledge_no = u_header[PACKET_SEQUENCE_NO_INDEX] + 1

        k_socket, address = (self.socket, (client_address[0], int(UDPTx)))
        print("Server Accepted Connection!")
        return self, address

    def close(self):  # fill in your code here
        server_packet = None
        print("IN CLOSE!!")
        if not self.is_server_established:
            self.socket.settimeout(0.2)
            p_header = udpPkt_hdr_data.pack(version, SOCK352_FIN, 0, 0, header_len, 404, 0, 0, self.sequence_no
                                            , self.acknowledge_no, 404, 0)
            try:
                self.socket.sendto(p_header, (self.server_address, int(UDPTx)))
                print("sent fin to server")
                server_packet, server_address = self.socket.recvfrom(header_len)
            except syssock.timeout:
                print("Error: Timed out!")

            while not server_packet:
                try:
                    server_packet, server_address = self.socket.recvfrom(header_len)
                except syssock.timeout:
                    print("Error: Timed out!")

            u_header = udpPkt_hdr_data.unpack(server_packet)
            if (SOCK352_FIN & SOCK352_ACK) == u_header[PACKET_FLAG_INDEX]:
                print("got fin ack")
                self.acknowledge_no = u_header[PACKET_SEQUENCE_NO_INDEX] + 1
                self.sequence_no = u_header[PACKET_ACK_NO_INDEX]
                p_header = udpPkt_hdr_data.pack(version, SOCK352_ACK, 0, 0, header_len, 404, 0, 0, self.sequence_no
                                                , self.acknowledge_no, 404, 0)
                try:
                    self.socket.sendto(p_header, (self.server_address, int(UDPTx)))
                    print("sending ack")
                except syssock.timeout:
                    return
            else:
                pass

            try:
                print("Client socket closed successfully! 2")
                self.socket.close()
            except:
                print("Error: Socket has already been closed!")

        else:
            client_packet, client_address = self.socket.recvfrom(header_len)
            u_header = udpPkt_hdr_data.unpack(client_packet)

            if SOCK352_FIN == u_header[PACKET_FLAG_INDEX]:
                print("got fin")
                self.acknowledge_no = u_header[PACKET_SEQUENCE_NO_INDEX] + 1
                self.sequence_no = u_header[PACKET_ACK_NO_INDEX]
                p_header = udpPkt_hdr_data.pack(version, (SOCK352_FIN & SOCK352_ACK), 0, 0, header_len, 404, 0, 0
                                                , self.sequence_no + 1, self.acknowledge_no, 404, 0)
                self.socket.sendto(p_header, (client_address[0], int(UDPTx)))
                print("sent fin ack")
                client_packet, client_address = self.socket.recvfrom(header_len)

                u_header = udpPkt_hdr_data.unpack(client_packet)
                if SOCK352_ACK == u_header[PACKET_FLAG_INDEX]:
                    print("got ack")
                    self.socket.close()
                    print("Server socket closed successfully!")

        return

    def create_data_packets(self, buffer):

        # total packets needed to transmit the entire buffer
        total_packets = int(len(buffer) / MAXIMUM_PAYLOAD_SIZE)
        if len(buffer) % MAXIMUM_PAYLOAD_SIZE != 0:
            total_packets += 1

        payload_len = MAXIMUM_PAYLOAD_SIZE

        for i in range(0, total_packets):
            if i == total_packets - 1:
                if len(buffer) % MAXIMUM_PAYLOAD_SIZE != 0:
                    payload_len = len(buffer) % MAXIMUM_PAYLOAD_SIZE

            new_packet = self.create_packet(flags=0x0,seq_no=self.sequence_no, ack_no=self.acknowledge_no,
                                            payload=buffer[MAXIMUM_PAYLOAD_SIZE * i:MAXIMUM_PAYLOAD_SIZE * (i+1)])
            self.sequence_no += 1
            self.acknowledge_no += 1
            self.data_packets.append(new_packet)
        return total_packets

    def send(self, buffer):  # fill in your code here

        byte_sent = 0
        current_seq = 0
        self.sequence_no = 0
        self.socket.settimeout(None)

        def recv_thread():
            k_seq_no = self.sequence_no
            time_tracker = int(round(time.time() * 1000))
            while k_seq_no < len(buffer):
                payload_len = 0
                if k_seq_no + self.fragment_size > len(buffer):
                    b_fragment = buffer[k_seq_no:]
                    payload_len = len(b_fragment)
                else:
                    b_fragment = buffer[k_seq_no:k_seq_no + self.fragment_size]
                    payload_len = self.fragment_size
                p_header = udpPkt_hdr_data.pack(version, SOCK352_SYN, 0, 0, header_len, 404, 0, 0, k_seq_no, self.acknowledge_no, 404, payload_len)
                # we've to pass data_packets in sendto

                self.socket.sendto(p_header + b_fragment, (self.server_address, int(UDPTx)))
                self.lock.acquire()

                if int(round(time.time() * 1000)) - time_tracker > 200:
                    if self.go_back_n:
                        self.go_back_n = False
                        return
                    time_tracker = int(round(time.time() * 1000))
                    print('Error: Timed out (recv_thread)!')
                else:
                    self.sequence_no = k_seq_no
                    k_seq_no += payload_len
                self.lock.release()

        total_packets = self.create_data_packets(buffer)

        thread = threading.Thread(target=recv_thread)
        thread.start()
        print('Started data pkt transmission...')

#        total_packets = self.create_data_packets(buffer)

        while byte_sent < len(buffer):
            try:
                server_packet, address = self.socket.recvfrom(header_len)
            except syssock.timeout:
                self.lock.acquire()
                self.go_back_n = True
                thread.join()
                self.sequence_no = current_seq
                byte_sent = current_seq
                thread = threading.Thread(target=recv_thread)
                thread.start()
                print('Socket Timeout, starting go-back-n...')
                self.lock.release()
                continue
            u_header = udpPkt_hdr_data.unpack(server_packet)
            if SOCK352_ACK == u_header[PACKET_FLAG_INDEX]:
                current_seq = u_header[PACKET_ACK_NO_INDEX]
                byte_sent = current_seq
                self.acknowledge_no = u_header[PACKET_SEQUENCE_NO_INDEX]
        print("Packet sent successfully!")
        return byte_sent

    def recv(self, nbytes):  # fill in your code here
        bytes_received =  bytearray()
        self.acknowledge_no = 0
        total_packet = 0
        while not nbytes <= 0:
            (packet, address) = self.socket.recvfrom(header_len + self.fragment_size)
            header = packet[:header_len]
            u_header = udpPkt_hdr_data.unpack(header)


            print(u_header)
            if self.acknowledge_no == u_header[PACKET_SEQUENCE_NO_INDEX] and \
                    SOCK352_SYN == u_header[PACKET_FLAG_INDEX]:
                self.sequence_no = u_header[PACKET_ACK_NO_INDEX]
                self.acknowledge_no = u_header[PACKET_SEQUENCE_NO_INDEX] + u_header[PACKET_PAYLOAD_LEN
]
 
                bytes_received.extend(packet[header_len:u_header[PACKET_PAYLOAD_LEN] + header_len])
                nbytes -= u_header[PACKET_PAYLOAD_LEN]
                p_header = udpPkt_hdr_data.pack(version, SOCK352_ACK, 0, 0, header_len, 404, 0, 0, self.sequence_no
                                                , self.acknowledge_no, 404, 0)
                self.socket.sendto(p_header, (address[0], int(UDPTx)))
            total_packet += 1
        print("A single packet received!")

        return bytes_received

    @staticmethod
    def create_header(flags, sequence_no, acknowledge_no, payload_len):
        return udpPkt_hdr_data.pack(0x1, flags, 0x0, 0x0, header_len, 0x0, 0x0, 0x0, sequence_no,
                                    acknowledge_no, 0x0, payload_len)
