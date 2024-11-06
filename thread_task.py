import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QWidget, QPushButton, QFileDialog)
from PySide6.QtCore import QThread, Signal, QTimer
from queue import Queue
from record_convert import RecordHeader, LidarData
import numpy as np
import pyqtgraph.opengl as gl
import time
import traceback
from view_play_state import PlayStateEnum
import open3d as o3d
import zmq

class PlyPubTask(QThread):
    finished = Signal()
    data_ready = Signal(object, object)
    def __init__(self, filename, speed=1.0):
        super().__init__()
        self.filename = filename
        self._is_running = True
        self.last_timestamp = 0.0
        self.speed = speed
        self.play_state = PlayStateEnum.PAUSED.value

        self.last_ply_count = 0

    def run(self):
        with open(self.filename, 'rb') as f:
            while self._is_running:
                if self.play_state == PlayStateEnum.PLAYING.value:
                    try:
                        timestamp, _, data = RecordHeader.read_record_head_a_data(f, 'lidar_data')
                        if not data:
                            break

                        points, colors = LidarData.get_lidar_points_np(data)

                        # 如果点云数量发生跳变超过1500，记录当前点云
                        ct = len(points)
                        if self.last_ply_count - ct > 1500 and self.last_ply_count > 0:
                            self.save_point_cloud(points, f'{timestamp}_{ct}.pcd')
                        self.last_ply_count = ct

                        # 临时帧率控制，没有考虑真实时间戳
                        time.sleep((min(self.last_timestamp, timestamp - self.last_timestamp)) / self.speed)
                        self.last_timestamp = timestamp

                        self.data_ready.emit(points, colors)  # 发射信号

                    except Exception as e:
                        traceback.print_exc()
                        break
                elif self.play_state == PlayStateEnum.PAUSED.value:
                    time.sleep(0.1)
                else:
                    break
            self.finished.emit()

    def stop(self):
        self._is_running = False

    def set_speed(self, speed):
        self.speed = speed

    def set_play_state(self, play_state):
        self.play_state = play_state

    def save_point_cloud(self, points, filename):
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        print(f'保存异常点云文件: {filename}')
        o3d.io.write_point_cloud(filename, pcd)

class ZmqPlyPubTask(QThread):
    finished = Signal()
    data_ready = Signal(object, object)
    def __init__(self, zmq_host: str, zmq_port: str):
        super().__init__()
        self.zmq_host = zmq_host
        self.zmq_port = zmq_port
        self.context = zmq.Context()
        self.zmq_socket = self.context.socket(zmq.SUB)
        self.zmq_socket.connect('tcp://{}:{}'.format(self.zmq_host, self.zmq_port))
        self.zmq_socket.setsockopt_string(zmq.SUBSCRIBE, '')
        self._is_running = True

    def run(self):
        try:
            while self._is_running:
                try:
                    data = self.zmq_socket.recv(flags=zmq.NOBLOCK)
                    points, colors = LidarData.get_lidar_points_np(data)

                    # 如果点云数量发生跳变超过1500，记录当前点云
                    ct = len(points)
                    if self.last_ply_count - ct > 1500 and self.last_ply_count > 0:
                        self.save_point_cloud(points, f'{time}_{ct}.pcd')
                    self.last_ply_count = ct

                    self.data_ready.emit(points, colors)  # 发射信号
                except zmq.Again:
                    self.sleep(0.001)
                    break
        finally:
            print('Cleaning up ZmqService...')
            self.zmq_socket.close()
            self.context.term()

    def stop(self):
        self._is_running = False