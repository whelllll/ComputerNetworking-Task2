================================================================
  Task2 UDP Reliable Transport — 程序运行说明文档
================================================================

1. 运行环境
-----------
- Python 3.8+
- 操作系统: Windows 11 (Host OS, 运行 Client) + WSL2 Ubuntu (Guest OS, 运行 Server)
- 无第三方依赖，仅使用 Python 标准库 (socket, struct, random, time, datetime)

2. 文件清单
-----------
  udp_protocol.py       — 共享协议模块（报文打包/解包 + 日志 + 学号验证）
  udpserver.py          — UDP Server 端程序（握手验证 + 单独确认 + 丢包模拟）
  udpclient.py          — UDP Client 端程序（三次握手 + SR滑动窗口（选择性重传） + 超时重传）
  test_input.txt        — 测试用英文 ASCII 输入文件（2400字节 = 30块 × 80B）
  readme.txt            — 本说明文档

3. 启动方式
-----------

  Step 1: Guest OS (WSL2 Ubuntu) 启动 Server
  -------------------------------------------
  cd /mnt/c/Users/65770/Desktop/计网课设/Task2\ UDP/
  python3 udpserver.py

  Server 默认监听 0.0.0.0:12345。启动后无输出，等待 Client 连接。

  Step 2: Host OS (Windows) 启动 Client
  -----------------------------------------
  cd 到 Task2 UDP 目录
  py udpclient.py

  Client 默认连接 172.18.136.238:12345（WSL2 IP）。
  如需修改 IP/端口，编辑 udpclient.py 第16行 server_addr。

4. 输出文件
-----------
  run_log.txt               — 运行日志（含每次收发的精确时间戳，与 Wireshark 对照）
  udp_received_output.txt   — Server 端按序交付后拼成的完整输出文件

5. 自定义协议说明
-----------------
  头部格式：Type(1B) + StudentID(2B) + SeqNum(1B) + DataLen(1B) = 5字节

  HEADER_FMT = "!B H B B"

  5 种报文类型：

    Type=0x01 SYN:       [Type:1B][StudentID:2B][0:1B][0:1B]
      Client -> Server，握手指令，携带学号验证字段

    Type=0x02 SYN-ACK:   [Type:1B][0:2B][0:1B][0:1B]
      Server -> Client，握手确认

    Type=0x03 DATA:      [Type:1B][0:2B][SeqNum:1B][DataLen:1B][Data:DataLenB]
      Client -> Server，承载数据块

    Type=0x04 ACK:       [Type:1B][0:2B][SeqNum:1B][0:1B]
      Server -> Client，单独确认，ACK(N)表示第N号包已收到

    Type=0x05 FIN:       [Type:1B][0:2B][0:1B][0:1B]
      Client -> Server，传输结束通知

6. 学号验证说明
---------------
  StudentID 字段 = 学号后4位(2821) XOR 0x5A3C = 20793
  Server 验证：收到值 XOR 0x5A3C，检验是否为合法4位数(0~9999)且等于2821。
  验证失败则拒绝连接，打印错误信息。

7. 可靠传输机制说明
-------------------
  本程序在应用层模拟 TCP 的可靠传输，替代 UDP 的不可靠特性：

  连接建立（模拟三次握手）:
    Client 发送 SYN 报文携带 StudentID
    Server 验证通过后回复 SYN-ACK
    Client 收到 SYN-ACK 后进入数据传输阶段

  滑动窗口（SR 协议（选择性重传））:
    发送窗口固定 400 字节 = 5 个包 × 80 字节/包
    Client 先发完窗口内所有包，统一等待 ACK
    收到单独 ACK(N) 后窗口右滑到 N+1
    窗口滑动后才能发送新包

  丢包模拟（Server 端）:
    Server 对每个到达的 DATA 包以 20% 概率模拟丢弃（不发 ACK）

  乱序处理（Server 端）:
    维护 expected 变量记录期望的下一个包号
    不论是否按序，到达的包先全部缓存到 buffer
    乱序到达的包先缓存到buffer，等前面缺失的包补齐后连续交付

  单独确认（Server 端）:
    ACK(N) 表示 第 N 号包已收到
    收到 ACK(N) 后 base 跳到 N+1

  超时重传（Client 端）:
    超时时间默认 300ms
    超时后仅重发窗口内超时的未确认包（SR 风格，非 GBN 整窗重发）
    收到 ACK 后计算 RTT 并记录

8. 测试数据说明
---------------
  test_input.txt: 2400 字节英文文本
  分块: 30 块 × 80 字节/块
  窗口: 5 包/窗口 (400B ÷ 80B = 5)

9. 输出统计
-----------
  Server 端: 总到达包数、按序接收数、模拟丢包数、丢包率
  Client 端: 丢包率、最大RTT、最小RTT、平均RTT

10. Wireshark 抓包要点
-----------------------
  - 过滤表达式: udp.port == 12345
  - 选择 Adapter for loopback（127.0.0.1 通信）或 WSL 虚拟网卡
  - 五种报文通过 payload 首字节区分：01/02/03/04/05
  - 截图时间戳与 run_log.txt 中的时间戳相互对照

11. 与 Task1 TCP 的关键区别
----------------------------
  | 特性       | Task1 TCP            | Task2 UDP            |
  |-----------|----------------------|----------------------|
  | 传输层     | TCP (SOCK_STREAM)    | UDP (SOCK_DGRAM)     |
  | 连接模型   | 内核三次握手          | 应用层模拟握手         |
  | 可靠性     | 内核保证              | 应用层SR协议保证      |
  | 丢包处理   | 内核自动重传          | 应用层超时重传         |
  | 报文边界   | 流式(需recv_exact)   | 数据报(天然保边界)     |
  | 并发       | 多线程accept          | 单线程recvfrom        |
  | 协议复杂度 | TLV 4种报文          | 自定义5种报文          |

================================================================
  作者: 彭欣雨  学号: 241002821  班级: 计算机24-2
================================================================
