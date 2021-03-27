import datetime
import dpkt
from collections import OrderedDict

FILE_PATH = "assignment2.pcap"
TCP_COUNT = 0
COUNT = 0
SENDER = "130.245.145.12"
RECEIVER = "128.208.2.198"
REQUESTS = {}
TRANSACTION = {}
THROUGHPUT = {}
PACKET = {}

INITIAL_SEQ_ACK = {}
SEQ_TO_ACK = {}

PACKETS = {}

class Packet():
    def __init__(self, data):
        self.ethernet = dpkt.ethernet.Ethernet(data)
        self.ip = self.ethernet.data
        self.tcp = self.ip.data
    
    def get_id(self):
        return (self.tcp.sport, get_ip(self.ip.src), self.tcp.dport, get_ip(self.ip.dst))

    def get_tcp_size(self):
        return len(self.tcp)

    def get_payload_size(self):
        return len(self.tcp.data)

    def get_tcp_flags(self):
        return self.tcp.flags

    def get_seq(self):
        return self.tcp.seq

    def get_ack(self):
        return self.tcp.ack

    def get_window_size(self):
        return self.tcp.win

    def get_src(self):
        return get_ip(self.ip.src)

class Flow():
    def __init__(self, sender, receiver):
        self.sender = sender
        self.receiver = receiver

        # combine packets
        self.flow = sorted(self.sender + self.receiver, key=lambda x: x[0])
        # find handshake
        self.__separate_handshake()
        # get window size scaling factor
        options = dpkt.tcp.parse_opts(self.handshake[0][-1].tcp.opts)
        window_scale = [value for opt,value in options if opt == dpkt.tcp.TCP_OPT_WSCALE][0]
        self.win_scaling = 2**int(window_scale.hex(),base=16)
        

    def __separate_handshake(self):
        # get the syn packet from sender
        sender_syn = None
        for packet in self.sender:
            if packet[-1].get_tcp_flags() == 0x2:
                sender_syn = packet
                break
        # get the syn, ack packet from receiver who's ack is 1 more than seq of the sender's syn packet
        receiver_syn = None
        for packet in self.receiver:
            if packet[-1].get_tcp_flags() == 0x12 and packet[-1].get_ack() == sender_syn[-1].get_seq()+1:
                receiver_syn = packet
                break
        # get the ack packet from sender who's ack is 1 more than seq of syn,ack packet
        sender_ack = None
        for packet in self.sender:
            if packet[-1].get_tcp_flags() == 0x10 and packet[-1].get_ack() == receiver_syn[-1].get_seq()+1:
                sender_ack = packet
                break
        # get index in flow
        index_to_split = self.flow.index(sender_ack)
        self.handshake = self.flow[:index_to_split+1]
        # check if the sender_ack is piggyback
        if sender_ack[-1].get_payload_size() != 0: # sender_ack is piggyback
            index_to_split -= 1
        self.flow = self.flow[index_to_split+1:]

    def get_id(self):
        return self.sender[0][-1].get_id()

    def get_transactions(self, start=0, end=2):
        return [(packet[-1].get_seq(), packet[-1].get_ack(), packet[-1].get_window_size()*self.win_scaling) for packet in self.flow if packet[-1].get_src() == SENDER][start:end]

    def get_throughput(self):
        # find the fin,ack from receiver
        last_packet = None
        for packet in self.receiver:
            if packet[-1].get_tcp_flags() == 0x11:
                last_packet == packet
        # get index of last packet in flow
        index = self.flow.index(packet)
        flow_in_period = self.flow[:index+1]
        data_sent = sum([packet[-1].get_tcp_size() for packet in flow_in_period if packet[-1].get_src() == SENDER])
        period = flow_in_period[-1][1] - flow_in_period[0][1]

        return data_sent/period

def get_ip(data):
    """
    Returns the IP addresss encode as 4 bytes in as . dot separated string.
    """
    data = data.hex()
    return ".".join([str(int(data[i:i+2], base=16)) for i in range(0, len(data), 2)])

def get_tcp_flows(file):
    flows = {}
    actual_flows = []
    identification = []
    counter = 0
    pcap = dpkt.pcap.Reader(file)
    for timestamp, buf in pcap:
        counter += 1
        e = dpkt.ethernet.Ethernet(buf)
        # print("ethernet", len(e))
        if isinstance(e.data, dpkt.ip.IP):
            # print(e.dst, e.src, e.type)
            ip = e.data
            # print("ip", len(ip))
            if isinstance(ip.data, dpkt.tcp.TCP):
                tcp = ip.data
                # print("tcp", len(tcp))
                src = get_ip(ip.src)
                dst = get_ip(ip.dst)
                
                iden = (tcp.sport, src, tcp.dport, dst)
# str(datetime.datetime.utcfromtimestamp(timestamp))
                idenP = iden if src == SENDER else (tcp.dport, dst, tcp.sport, src)
                if idenP not in identification:
                    identification.append(idenP)
                flows[iden] = flows.get(iden, []) + [(counter, timestamp, Packet(buf))]
    for src_iden in identification:
        dest_iden = src_iden[2:] + src_iden[:2]
        actual_flows.append(Flow(flows[src_iden], flows[dest_iden]))
    
    return actual_flows

def process_pcap(file):
    global COUNT
    pcap = dpkt.pcap.Reader(f)
    # print(pcap)
    for timestamp, buf in pcap:
        COUNT += 1
        e = dpkt.ethernet.Ethernet(buf)
        # print("ethernet", len(e))
        if isinstance(e.data, dpkt.ip.IP):
            # print(e.dst, e.src, e.type)
            ip = e.data
            # print("ip", len(ip))
            if isinstance(ip.data, dpkt.tcp.TCP):
                tcp = ip.data
                # print("tcp", len(tcp))
                src = get_ip(ip.src)
                dst = get_ip(ip.dst)
                
                iden = (tcp.sport, src, tcp.dport, dst)
                # SEQ/ACK number
                combo = sorted([tcp.sport, tcp.dport]) + sorted([src, dst])
                combo = tuple(combo)
                if len(INITIAL_SEQ_ACK.get(combo, {})) == 0:
                    INITIAL_SEQ_ACK[combo] = {'SEQ': tcp.seq}
                elif len(INITIAL_SEQ_ACK.get(combo, {})) == 1:
                    INITIAL_SEQ_ACK[combo]['ACK'] = tcp.seq                    

                idenP = iden if src == SENDER else (tcp.dport, dst, tcp.sport, src)
                # idenP = iden
                PACKETS[idenP] = PACKETS.get(idenP, []) + [(COUNT, str(datetime.datetime.utcfromtimestamp(timestamp)), Packet(buf))]
                SEQ_TO_ACK[tcp.seq] = tcp.seq
                if REQUESTS.get(iden, False):
                    THROUGHPUT[iden] += len(tcp)
                    PACKET[iden] += 1
                    if len(TRANSACTION[iden]) == 0 and tcp.seq-INITIAL_SEQ_ACK[combo]['SEQ'] != 1:
                        # TRANSACTION[iden]["FIRST"] = (tcp.seq, tcp.ack, tcp.win)
                        TRANSACTION[iden]["FIRST"] = (tcp.seq-INITIAL_SEQ_ACK[combo]['SEQ'], tcp.ack-INITIAL_SEQ_ACK[combo]['ACK'], tcp.win)
                    elif len(TRANSACTION[iden]) == 1:
                        # TRANSACTION[iden]["SECOND"] = (tcp.seq, tcp.ack, tcp.win)
                        TRANSACTION[iden]["SECOND"] = (tcp.seq-INITIAL_SEQ_ACK[combo]['SEQ'], tcp.ack-INITIAL_SEQ_ACK[combo]['ACK'], tcp.win)
                if not (REQUESTS.get(iden, False)) and src == SENDER:
                    REQUESTS[iden] = COUNT
                    TRANSACTION[iden] = {}
                    THROUGHPUT[iden] = len(tcp)
                    PACKET[iden] = 1
                    # print(bin(tcp.flags))
                # if tcp.flags & 0x1 and src == SENDER:
                    # print(COUNT, iden)
                    # print(bin(tcp.flags))
                    # TCP_COUNT += 1

                # if src == SENDER:
                    # TCP_COUNT += 1

        # break

if __name__ == "__main__":
    with open(FILE_PATH, 'rb') as f:
        # process_pcap(f)
        result = get_tcp_flows(f)
        print(f"There are a total of {len(result)} TCP flows\n")
        for num, flow in enumerate(result, start=1):
            # print(flow)
            print(f"Flow {num} Information:")
            print("PART A")
            print(f"a) {flow.get_id()}")
            transactions = flow.get_transactions()
            print("b) The first 2 transactions:")
            for t_count, transaction in enumerate(transactions, start=1):
                print(f"Tranaction {t_count}: \n\tSequence number: {transaction[0]:,d}\n\tAck number: {transaction[1]:,d}\n\tReceive Window Size: {transaction[2]:,d}")
            print(f"c) Throughput: {flow.get_throughput():,f} bytes/second")
            print("="*100)