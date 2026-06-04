import socket
import time
import sys
from udp_protocol import pack_syn, pack_ack, pack_data, pack_fin, unpack_header, HEADER_SIZE, TYPE_SYN_ACK, TYPE_ACK, log

# ==================== 阶段0：准备数据 — N块 × chunk_size字节 ====================
with open("test_input.txt", "rb") as f:
    file_data = f.read()

chunk_size = 80
chunks = []
total_chunks = (len(file_data) + chunk_size - 1) // chunk_size
for i in range(total_chunks):
    start = i * chunk_size
    chunks.append(file_data[start:start + chunk_size])  # chunks[0]~chunks[N-1] 对应包号1~N

# UDP套接字 + 300ms超时（超时时间内收不到ACK则重传）
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.3)

# 命令行参数：py udpclient.py <服务器IP> <服务器端口>
if len(sys.argv) < 3:
    print("用法: py udpclient.py <serverIP> <serverPort>")
    print("示例: py udpclient.py 127.0.0.1 12345")
    sys.exit(1)
server_ip = sys.argv[1]
server_port = int(sys.argv[2])
server_addr = (server_ip, server_port)

# ==================== 阶段1：三次握手（应用层模拟） ====================
student_id = 20793  # 2821 XOR 0x5A3C 的结果
while True:
    sock.sendto(pack_syn(student_id), server_addr)  # ① 发送SYN + 学号
    log("发送SYN包，等待服务器响应")
    try:
        data, addr = sock.recvfrom(1024)
        typ, sid, seqnum, datalen = unpack_header(data)
        if typ == TYPE_SYN_ACK:
            log("收到SYN-ACK包，握手第二步成功")
            sock.sendto(pack_ack(0), server_addr)  # ③ 发送ACK完成握手
            log("发送ACK，三次握手完成")
            break
    except socket.timeout:
        log("握手超时重发SYN")  # 超时重发，直到收到SYN-ACK


# ==================== 阶段2：SR滑动窗口传输 ====================
base = 1        # 窗口左边界（最小未确认包号）
sent = {}       # 记录每个包的发包时间 {包号: 时间戳}，用于RTT计算和超时判断
acked = set()   # 已确认的包号集合（SR风格，不按序也行）
rtt_list = []   # 所有RTT值，最后统计最大/最小/平均

total_packets = len(chunks)
while base <= total_packets:
    # 发窗口内所有未发过的包（窗口大小=5）
    for seq in range(base, min(base + 5, total_packets + 1)):
        if seq not in sent:
            chunk = chunks[seq - 1]
            sock.sendto(pack_data(seq, chunk), server_addr)
            sent[seq] = time.time()  # 记录发包时间
            start_byte = (seq - 1) * 80 + 1
            end_byte = start_byte + len(chunk) - 1
            log(f"发送包{seq}，字节范围[{start_byte},{end_byte},client已发送]")

    # 等待ACK + 超时重传
    try:
        data, addr = sock.recvfrom(1024)
        typ, sid, ack_seq, datalen = unpack_header(data)

        if typ == TYPE_ACK and ack_seq not in acked:
            acked.add(ack_seq)
            rtt = (time.time() - sent[ack_seq]) * 1000  # RTT = 收到ACK时间 - 发包时间
            rtt_list.append(rtt)
            start_byte = (ack_seq - 1) * 80 + 1
            end_byte = start_byte + len(chunks[ack_seq - 1]) - 1
            log(f"收到ACK{ack_seq}，RTT={rtt:.2f}ms，字节范围[{start_byte},{end_byte},server已收到,RTT={rtt:.2f}ms]")

            # 窗口右滑：base连续确认就持续前进
            while base in acked:
                base = base + 1

    except (socket.timeout, ConnectionResetError):
        # 超时：单独重传窗口内已发未确认的包（SR风格，不是GBN重发全部）
        now = time.time()
        for seq in range(base, min(base + 5, total_packets + 1)):
            if seq not in acked and now - sent.get(seq, 0) >= 0.3:
                chunk = chunks[seq - 1]
                sock.sendto(pack_data(seq, chunk), server_addr)
                sent[seq] = now  # 更新发包时间
                start_byte = (seq - 1) * 80 + 1
                end_byte = start_byte + len(chunk) - 1
                log(f"包{seq}超时,单独重传，字节范围[{start_byte},{end_byte},client已重发]")

# ==================== 阶段3：结束连接 + 统计 ====================
sock.sendto(pack_fin(), server_addr)
log("发送FIN包，结束连接")

if rtt_list:
    log(f"最大RTT: {max(rtt_list):.1f}ms")
    log(f"最小RTT: {min(rtt_list):.1f}ms")
    log(f"平均RTT: {sum(rtt_list)/len(rtt_list):.1f}ms")

sock.close()
