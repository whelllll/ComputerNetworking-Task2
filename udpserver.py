import socket
import random
from udp_protocol import (unpack_header, verify_student_id, pack_syn_ack, pack_ack,
                          log_init, log, HEADER_SIZE, TYPE_SYN, TYPE_ACK, TYPE_DATA, TYPE_FIN)

log_init()

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(('0.0.0.0', 12345))

# ==================== 阶段1：三次握手（应用层模拟） ====================
while True:
    data, addr = server.recvfrom(1024)#收1的syn+学号
    if len(data) < HEADER_SIZE:#健壮性
        log(f"握手阶段收到异常短包: {data.hex()}")
        continue
    typ, student_id, seqnum, datalen = unpack_header(data[:HEADER_SIZE])

    if typ == TYPE_SYN:#判断学号
        if verify_student_id(student_id):
            log(f"握手第二步，来自{addr}的学生ID {student_id} 验证通过")
            server.sendto(pack_syn_ack(), addr)#发synack

            # 等待第三次握手ACK，加超时避免永久阻塞
            server.settimeout(3.0)
            # - 3秒内收到ACK → 正常完成握手，break 进入数据接收阶段
            #- 3秒内没收到 → 触发 socket.timeout 异常，被 except 捕获，重置超时为None，continue 回到外层循环继续监听新的SYN
            try:
                data, addr = server.recvfrom(1024)#收3
                if len(data) >= HEADER_SIZE:#健壮性
                    t, _, _, _ = unpack_header(data[:HEADER_SIZE])
                    if t == TYPE_ACK:
                        log("收到第三次握手ACK，握手完成")
                        break
            except socket.timeout:
                log("握手超时（未收到第三次ACK），回到监听状态")
                server.settimeout(None)
                continue
            server.settimeout(None)


        else:
            log(f"学号验证失败，拒绝连接")
    # 非SYN报文在握手阶段直接忽略，继续等待


# ==================== 阶段2：SR协议接收数据 ====================
buffer = {}       # 缓存乱序包 {包号: payload字节串}
recv_set = set()  # 已收到的包号，用于去重
total_data = 0    # 总到达包数（含重传和丢包）
drop_count = 0    # 模拟丢包数
expected = 1      # 期望的下一个包号
delivered_payloads = []  # 按序交付的 payload，最后写文件

while True:
    data, addr = server.recvfrom(4096)#1.收包
    if len(data) < HEADER_SIZE:#健壮性
        log(f"收到异常数据: {data.hex()}, 长度={len(data)}")
        continue
        #解包
    typ, student_id, seqnum, datalen = unpack_header(data[:HEADER_SIZE])

    if typ == TYPE_DATA:
        total_data += 1


        #去重+丢包 直接continue

        # 去重：已收过的包必须重发ACK（SR协议要求，ACK可能丢了）
        if seqnum in recv_set:
            log(f"收到重复包{seqnum}，重发ACK({seqnum})")
            server.sendto(pack_ack(seqnum), addr)#2发ack 后面的不管了 已经收过了
            continue

        # 模拟20%丢包
        if random.random() < 0.2:
            drop_count += 1#丢包注意这个数据++
            log(f"模拟丢包，丢弃序列号 {seqnum} 的数据包")
            continue


        
        #正常情况的处理


        # 提取 payload（去掉5字节头部）+发ack
        payload = data[HEADER_SIZE:]#先去掉
        recv_set.add(seqnum)#加入已收到包号
        buffer[seqnum] = payload #缓存
        log(f"收到包{seqnum}, payload长度={len(payload)}, 发ACK({seqnum})")
        server.sendto(pack_ack(seqnum), addr)#2.发ack

        # 连续交付：只要expected在缓存中就交付
        while expected in recv_set:
            payload = buffer.pop(expected)
            recv_set.discard(expected)
            delivered_payloads.append(payload)
            log(f"交付包{expected}，payload长度={len(payload)}")
            expected += 1

    elif typ == TYPE_FIN:#3收结束
        log("收到FIN包，连接结束")
        break

# ==================== 阶段3：写输出文件 + 统计 ====================
out_path = "udp_received_output.txt"
with open(out_path, "wb") as f:
    for payload in delivered_payloads:
        f.write(payload)
log(f"输出文件已写入 -> {out_path}，共 {len(delivered_payloads)} 块")

if total_data > 0:
    delivered = expected - 1
    log(f"总到达包数: {total_data}, 成功交付: {delivered}, 模拟丢包: {drop_count}")
    log(f"模拟丢包率: {drop_count / total_data * 100:.1f}%")
server.close()
log("服务器关闭")
