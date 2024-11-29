import threading
from thread_task import ZmqService, start_zmq_service
from typing import List
import time
import zmq
from datetime import datetime

def start_zmq_service(service: ZmqService):
    service.connect()
    message_count = 0
    last_time = time.time()
    while True:
        try:
            current_time = time.time()
            data = service.receive_data()
            message_count += 1
            
            # 每秒计算一次频率
            if current_time - last_time >= 1.0:
                hz = message_count / (current_time - last_time)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                      f"{service.zmq_host}:{service.zmq_port} 接收频率: {hz:.2f}Hz")
                message_count = 0
                last_time = current_time
        except zmq.Again:
            time.sleep(0.001)
            # break
        except Exception as e:
            print(f"未知错误: {e}")
            break

# # 创建3个ZmqService实例
services = [
    ZmqService("9.199.50.87", 5555),
    ZmqService("9.199.50.87", 5556)
    # ZmqService("9.199.50.87", 5558)
]

# 创建并启动线程
threads: List[threading.Thread] = []
for service in services:
    thread = threading.Thread(target=start_zmq_service, args=(service,))
    thread.daemon = True  # 设置为守护线程
    thread.start()
    threads.append(thread)

# 主线程保持运行
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n正在关闭服务...")
    # 清理资源
    for service in services:
        service.cleanup()

    # 等待所有线程结束
    for thread in threads:
        thread.join()
    
    print("所有服务已关闭")