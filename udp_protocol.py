import struct
from datetime import datetime

# 五种报文类型 — 通过首字节区分
TYPE_SYN = 0x01      # 握手请求
TYPE_SYN_ACK = 0x02  # 握手确认
TYPE_DATA = 0x03     # 数据包
TYPE_ACK = 0x04      # 确认包
TYPE_FIN = 0x05      # 结束连接

# 自定义协议头：Type(1B) + StudentID(2B) + SeqNum(1B) + DataLen(1B) = 5字节
# !BHBB = 网络字节序(大端): 1字节无符号 + 2字节无符号 + 1字节无符号 + 1字节无符号
HEADER_FMT = '!BHBB'
HEADER_SIZE = 5

def pack_syn(student_id):
    """打包SYN包 — 握手第一步，携带学号用于身份验证"""
    return struct.pack(HEADER_FMT, TYPE_SYN, student_id, 0, 0)

def pack_syn_ack():
    """打包SYN-ACK包 — 握手第二步，服务器同意连接"""
    return struct.pack(HEADER_FMT, TYPE_SYN_ACK, 0, 0, 0)

def pack_data(seq, data):
    """打包DATA包 — 头部5字节 + 数据载荷80字节 = 85字节总长"""
    header = struct.pack(HEADER_FMT, TYPE_DATA, 0, seq, len(data))
    return header + data

def pack_ack(seq):
    """打包ACK包 — 确认该包号已收到（SR风格单独确认）"""
    return struct.pack(HEADER_FMT, TYPE_ACK, 0, seq, 0)

def pack_fin():
    """打包FIN包 — 通知服务器传输结束"""
    return struct.pack(HEADER_FMT, TYPE_FIN, 0, 0, 0)

def unpack_header(data):
    """解包头部5字节 -> (type, student_id, seqnum, datalen)"""
    return struct.unpack(HEADER_FMT, data[:HEADER_SIZE])

def verify_student_id(received_id):
    """XOR验证学号：received_id ^ 0x5A3C == 2821 则通过
    20793 ^ 0x5A3C == 2821，计算结果即为打包时用的 student_id=20793"""
    return (received_id ^ 0x5A3C) == 2821

def log_init():
    """初始化日志文件，清空旧内容"""
    with open("run_log.txt", "w", encoding="utf-8") as f:
        f.write("")

def log(msg):
    """带时间戳的日志输出，同时写入文件和控制台"""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    line = f'[{ts}] {msg}'
    with open("run_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)
