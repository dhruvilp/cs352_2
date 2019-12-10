import binascii
import socket as syssock
import struct
import sys
import time
import threading
from random import randint

version = 0x1
sock352PktHdrData = "!BBBBHHLLQQLL"
PACKET_HEADER_LENGTH = struct.calcsize(sock352PktHdrData)
udpPkt_hdr_data = struct.Struct(sock352PktHdrData)

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


def init(UDPportTx, UDPportRx):
    global UDPRx, UDPTx
    UDPTx = UDPportTx
    UDPRx = UDPportRx


class socket:
    def __init__(self):
        self.socket = syssock.socket(syssock.AF_INET, syssock.SOCK_DGRAM)
        self.socket.settimeout(0.2)
        self.sequence_no = randint(1, 100000)
        self.ack_no = 0
        self.file_len = -1
        self.pack_sent = 0
        self.ack_recv = 0
        self.iterate = 2
        self.data_packets = []
        self.retransmit = False
        self.is_connected = False
        self.can_close = False
        self.can_send = True
        self.last_data_packet_acked = None
        self.send_address = None
        self.retransmit_lock = threading.Lock()
        self.ack_lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.recv_window = MAX_WINDOW
        self.buffer_size = MAX_WINDOW
        self.buffer = ""
        return

    def bind(self, address):
        self.socket.bind((address[0], int(UDPRx)))
        return

    def connect(self, address):
        global syn_ack_packet
        self.send_address = (address[0], int(UDPTx))
        print("Send address is: ", self.send_address)
        self.socket.bind((address[0], int(UDPRx)))
        if self.is_connected:
            print("Connection is already established!!!")
            return

        synPacket = self.createPacket(SOCK352_SYN, sequence_no=self.sequence_no)
        self.socket.sendto(synPacket, self.send_address)
        self.sequence_no += 1
        received_handshake_packet = False
        while not received_handshake_packet:
            try:
                (syn_ack_packet, addr) = self.socket.recvfrom(PACKET_HEADER_LENGTH)
                syn_ack_packet = struct.unpack(sock352PktHdrData, syn_ack_packet)
                if syn_ack_packet[PACKET_FLAG_INDEX] == SOCK352_RESET:
                    print("Connection reset by the server!!!")
                    return
                if syn_ack_packet[PACKET_FLAG_INDEX] == SOCK352_SYN | SOCK352_ACK:
                    received_handshake_packet = True
                if syn_ack_packet[PACKET_ACK_NO_INDEX] != self.sequence_no:
                    received_handshake_packet = False
            except syssock.timeout:
                self.socket.sendto(synPacket, self.send_address)

        self.ack_no = syn_ack_packet[PACKET_SEQUENCE_NO_INDEX] + 1
        ackPacket = self.createPacket(flags=SOCK352_ACK,
                                      sequence_no=self.sequence_no,
                                      ack_no=self.ack_no)
        self.sequence_no += 1
        self.is_connected = True
        self.socket.sendto(ackPacket, self.send_address)
        print("Client is connected to the server at %s:%s" % (self.send_address[0], self.send_address[1]))

    def listen(self, backlog):
        pass

    def accept(self):
        global syn_packet, addr, ack_packet
        if self.is_connected:
            print("Error: Connection is already established!!!")
            return
        got_connection_request = False
        while not got_connection_request:
            try:
                (syn_packet, addr) = self.socket.recvfrom(PACKET_HEADER_LENGTH)
                syn_packet = struct.unpack(sock352PktHdrData, syn_packet)
                if syn_packet[PACKET_FLAG_INDEX] == SOCK352_SYN:
                    got_connection_request = True
                if syn_packet[PACKET_FLAG_INDEX] == SOCK352_SYN | SOCK352_HAS_OPT:
                    got_connection_request = True

            except syssock.timeout:
                pass

        flags = SOCK352_SYN | SOCK352_ACK
        syn_ack_packet = self.createPacket(flags=flags,
                                           sequence_no=self.sequence_no,
                                           ack_no=syn_packet[PACKET_SEQUENCE_NO_INDEX] + 1)
        self.sequence_no += 1
        self.socket.sendto(syn_ack_packet, addr)
        got_final_ack = False
        while not got_final_ack:
            try:
                (ack_packet, addr) = self.socket.recvfrom(PACKET_HEADER_LENGTH)
                ack_packet = struct.unpack(sock352PktHdrData, ack_packet)
                if ack_packet[PACKET_FLAG_INDEX] == SOCK352_ACK:
                    got_final_ack = True
            except syssock.timeout:
                self.socket.sendto(syn_ack_packet, addr)
        self.ack_no = ack_packet[PACKET_SEQUENCE_NO_INDEX] + 1
        self.send_address = (addr[0], int(UDPTx))
        self.is_connected = True
        print("Server is now connected to the client at %s:%s" % (self.send_address[0], self.send_address[1]))
        return self, addr

    def close(self):
        if not self.is_connected:
            print("No connection is currently established!")
            return
        if self.can_close:
            self.socket.close()
            self.send_address = None
            self.is_connected = False
            self.can_close = False
            self.sequence_no = randint(1, 100000)
            self.ack_no = 0
            self.data_packets = []
            self.file_len = -1
            self.retransmit = False
            self.last_data_packet_acked = None
        else:
            print("Failed to close the connection!")

    def create_data_packets(self, buffer):
        total_packets = (int)(len(buffer) / MAXIMUM_PAYLOAD_SIZE)
        if len(buffer) % MAXIMUM_PAYLOAD_SIZE != 0:
            total_packets += 1
        payload_len = MAXIMUM_PAYLOAD_SIZE

        for i in range(0, total_packets):
            if i == total_packets - 1:
                if len(buffer) % MAXIMUM_PAYLOAD_SIZE != 0:
                    payload_len = len(buffer) % MAXIMUM_PAYLOAD_SIZE
            new_packet = self.createPacket(flags=0x0,
                                           sequence_no=self.sequence_no,
                                           ack_no=self.ack_no,
                                           payload_len=payload_len)
            self.sequence_no += 1
            self.ack_no += 1
            self.data_packets.append(new_packet)

        return total_packets

    def send(self, buffer):
        if self.file_len == -1:
            self.socket.sendto(buffer, self.send_address)
            self.file_len = struct.unpack("!L", buffer)[0]
            print("File length sent: " + str(self.file_len) + " bytes")
            return self.file_len

        start_sequence_no = self.sequence_no
        total_packets = self.create_data_packets(buffer)

        recv_ack_thread = threading.Thread(target=self.recv_acks, args=())
        recv_ack_thread.setDaemon(True)
        recv_ack_thread.start()

        print("-------Started data packet transmission...-------")
        print("Total packets: " + str(total_packets))
        while not self.can_close:
            if self.last_data_packet_acked is None:
                resend_start_index = 0
            else:
                resend_start_index = int(self.last_data_packet_acked[PACKET_ACK_NO_INDEX]) - start_sequence_no
            if resend_start_index == total_packets:
                self.can_close = True
            self.retransmit_lock.acquire()
            self.retransmit = False
            self.retransmit_lock.release()
            while not self.can_close and resend_start_index < total_packets and not self.retransmit:
                try:
                    if self.can_send is True:
                        self.ack_lock.acquire()
                        self.ack_recv = 0
                        self.ack_lock.release()
                        self.pack_sent = 0
                        count = 0
                        iter_bytes = 0
                        for i in range(self.iterate):
                            if resend_start_index + i < total_packets and iter_bytes < self.recv_window:
                                if iter_bytes + len(self.data_packets[resend_start_index + i]) > self.recv_window:
                                    self.divide_pkt(resend_start_index + i, self.recv_window - iter_bytes)
                                    total_packets += 1
                                iter_bytes += len(self.data_packets[resend_start_index + i])
                                count += 1
                        print("Packets to send: " + str(count))
                        for i in range(count):
                            self.socket.sendto(self.data_packets[resend_start_index], self.send_address)
                            self.pack_sent += 1
                            resend_start_index += 1
                        self.send_lock.acquire()
                        self.can_send = False
                        self.send_lock.release()
                except syssock.error as error:
                    if error.errno != 111:
                        raise error
                    self.can_close = True
                    break
        recv_ack_thread.join()
        fin_packet = self.createPacket(flags=SOCK352_FIN,
                                       sequence_no=self.sequence_no + 1,
                                       ack_no=self.ack_no + 1,
                                       window=MAX_WINDOW)
        self.socket.sendto(fin_packet, self.send_address)
        print("-------Finished transmitting data packets-------")
        return len(buffer)

    def divide_pkt(self, index, val):
        packet = self.data_packets[index]
        packet_header = packet[:PACKET_HEADER_LENGTH]
        packet_data = packet[PACKET_HEADER_LENGTH:]
        packet_header = struct.unpack(sock352PktHdrData, packet_header)
        seq_no = packet_header[PACKET_SEQUENCE_NO_INDEX]
        ack_no = packet_header[PACKET_ACK_NO_INDEX]
        send1 = packet_data[:val - 40]
        send2 = packet_data[val - 40:]
        packet1 = self.createPacket(flags=0x0,
                                    sequence_no=seq_no,
                                    ack_no=ack_no,
                                    payload_len=len(send1))
        packet2 = self.createPacket(flags=0x0,
                                    sequence_no=seq_no + 1,
                                    ack_no=ack_no + 1,
                                    payload_len=len(send2))
        self.data_packets.insert(index, packet2 + send2)
        self.data_packets.insert(index, packet1 + send1)
        self.data_packets.pop(index + 2)

        for i in range(index + 2, len(self.data_packets)):
            pack = self.data_packets[i]
            pack_header = pack[:PACKET_HEADER_LENGTH]
            pack_data = pack[PACKET_HEADER_LENGTH:]
            pack_header = struct.unpack(sock352PktHdrData, pack_header)
            seq = pack_header[PACKET_SEQUENCE_NO_INDEX]
            ack = pack_header[PACKET_ACK_NO_INDEX]
            packet = self.createPacket(flags=0x0,
                                       sequence_no=seq + 1,
                                       ack_no=ack + 1,
                                       payload_len=len(pack_data))
            self.data_packets[i] = packet + pack_data

    def recv_acks(self):
        while not self.can_close:
            try:
                new_packet = self.socket.recv(PACKET_HEADER_LENGTH)
                new_packet = struct.unpack(sock352PktHdrData, new_packet)
                self.recv_window = new_packet[WINDOW_INDEX]
                if self.recv_window == 0:
                    self.send_lock.acquire()
                    self.can_send = False
                    self.send_lock.release()
                if self.recv_window != 32000:
                    self.ack_lock.acquire()
                    self.ack_recv += 1
                    self.ack_lock.release()
                if self.ack_recv == self.pack_sent and self.can_send is False and self.recv_window > 0:
                    self.iterate *= 2
                    self.send_lock.acquire()
                    self.can_send = True
                    self.send_lock.release()
                if new_packet[PACKET_FLAG_INDEX] != SOCK352_ACK:
                    continue
                if (self.last_data_packet_acked is None or
                        new_packet[PACKET_SEQUENCE_NO_INDEX] > self.last_data_packet_acked[
                            PACKET_SEQUENCE_NO_INDEX]):
                    self.last_data_packet_acked = new_packet

            except syssock.timeout:
                self.retransmit_lock.acquire()
                self.retransmit = True
                self.retransmit_lock.release()

            except syssock.error as error:
                if error.errno != 111:
                    self.can_close = True
                    raise error

        print("recv window after all ACKs: " + str(self.recv_window))

    def recv(self, nbytes):
        data_received = bytearray()
        if self.file_len == -1:
            file_size_packet = self.socket.recv(struct.calcsize("!L"))
            self.file_len = struct.unpack("!L", file_size_packet)[0]
            print("File Length Received: " + str(self.file_len) + " bytes")
            return file_size_packet
        bytes_to_receive = nbytes
        full = False
        print("# of bytes to recv : " + str(bytes_to_receive))
        print("-------Started receiving data packets...-------")
        while bytes_to_receive > 0 and full is False:
            if self.buffer_size <= 0:
                self.buffer_size = MAX_WINDOW
                ackPacket = self.createPacket(flags=SOCK352_ACK,
                                              sequence_no=self.sequence_no - 1,
                                              ack_no=self.ack_no,
                                              window=MAX_WINDOW)
                self.socket.sendto(ackPacket, self.send_address)
            try:
                packet_received = self.socket.recv(self.buffer_size)
                self.buffer_size = self.buffer_size - len(packet_received)
                print("After receiving packet, the window: " + str(self.buffer_size))
                if bytes_to_receive - len(packet_received) < 0:
                    full = True
                    print("--------Buffer is full!!!!!-------")
                else:
                    bytes_to_receive = bytes_to_receive - len(packet_received)
                    print("# of bytes now: " + str(bytes_to_receive))
                str_received = self.manage_recvd_data_packet(packet_received, self.buffer_size)
                if str_received is not None:
                    self.buffer += str(str_received)

            except syssock.timeout:
                pass

        self.can_close = True
        print("-------Finished receiving the data-------")
        return data_received

    def createPacket(self, flags=0x0, sequence_no=0x0, ack_no=0x0, payload_len=0x0, window=0x0):
        return udpPkt_hdr_data.pack(0x1, flags, 0x0, 0x0, PACKET_HEADER_LENGTH,
                                    0x0, 0x0, 0x0, sequence_no, ack_no, window, payload_len)

    def manage_recvd_data_packet(self, packet, window):
        packet_header = packet[:PACKET_HEADER_LENGTH]
        packet_data = packet[PACKET_HEADER_LENGTH:]
        packet_header = struct.unpack(sock352PktHdrData, packet_header)
        if packet_header[PACKET_SEQUENCE_NO_INDEX] != self.ack_no:
            return
        self.data_packets.append(packet_data)
        self.ack_no += 1
        ackPacket = self.createPacket(flags=SOCK352_ACK,
                                      sequence_no=self.sequence_no,
                                      ack_no=self.ack_no,
                                      window=window)
        self.sequence_no += 1
        self.socket.sendto(ackPacket, self.send_address)
        return packet_data
