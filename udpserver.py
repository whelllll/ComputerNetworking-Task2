import socket
import random
from udp_protocol import unpack_header, verify_student_id, pack_syn_ack, pack_ack, log_init, log, HEADER_SIZE, TYPE_SYN, TYPE_ACK, TYPE_DATA, TYPE_FIN

log_init()

# UDP套接字 — SOCK_DGRAM是数据报模式，天然保留报文边界
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(('0.0.0.0', 12345))  # 监听所有网卡

# ==================== 阶段1：三次握手（应用层模拟） ====================
while True:
    data, addr = server.recvfrom(1024)
    typ, student_id, seqnum, datalen = unpack_header(data[:HEADER_SIZE])

    if typ == TYPE_SYN:
        # 验证学号：收到的值 XOR 0x5A3C 必须等于 2821
        if verify_student_id(student_id):
            log(f"握手第二步，来自{addr}的学生ID {student_id} 验证通过")
            server.sendto(pack_syn_ack(), addr)  # ② 回复SYN-ACK

            # 等待第三次握手ACK
            data, addr = server.recvfrom(1024)
            if len(data) >= HEADER_SIZE:  # 防御：过滤异常短包
                t, _, _, _ = unpack_header(data[:HEADER_SIZE])
                if t == TYPE_ACK:
                    log("收到第三次握手ACK，握手完成")
                    break  # 握手成功，进入数据传输阶段
        else:
            log(f"学号验证失败，拒绝连接")


# ==================== 阶段2：SR协议接收数据 ====================
buffer = {}      # 缓存乱序包 {包号: 原始数据}，用于后续交付
recv_set = set()  # 记录已收到的包号，用于去重和判断连续
total_data = 0    # 总到达包数（含重传）
drop_count = 0    # 模拟丢包数
expected = 1      # 期望的下一个包号，用于按序交付

while True:
    data, addr = server.recvfrom(4096)
    if len(data) < HEADER_SIZE:
        log(f"收到异常数据: {data.hex()}, 长度={len(data)}")
        continue

    typ, student_id, seqnum, datalen = unpack_header(data[:HEADER_SIZE])

    if typ == TYPE_DATA:
        total_data += 1

        # 去重：已收过的包直接忽略
        if seqnum in recv_set:
            continue

        # 模拟20%丢包 — 不发ACK，客户端超时后会重传
        if random.random() < 0.2:
            drop_count += 1
            log(f"模拟丢包，丢弃序列号 {seqnum} 的数据包")
            continue

        # SR核心：不管是否乱序，先缓存下来
        recv_set.add(seqnum)
        buffer[seqnum] = data
        log(f"收到包{seqnum},长度{len(data)},发ACK({seqnum})")
        server.sendto(pack_ack(seqnum), addr)  # 单独对每个包发ACK

        # 连续交付：只要expected号在缓存中就交付并右移
        while expected in recv_set:
            delivered = buffer.pop(expected)
            recv_set.discard(expected)
            log(f"交付包{expected}，长度{len(delivered)}")
            expected += 1

    elif typ == TYPE_FIN:
        log("收到FIN包，连接结束")
        break

# ==================== 阶段3：统计输出 ====================
if total_data > 0:
    delivered = expected - 1  # expected-1 就是实际交付的包数
    log(f"总到达包数：{total_data},成功交付：{delivered},模拟丢包：{drop_count}")
    log(f"模拟丢包率：{drop_count/total_data *100:.1f}%")
log("服务器关闭")
