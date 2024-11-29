import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QWidget, QPushButton, QFileDialog)
from PySide6.QtCore import QThread, Signal, QTimer
from queue import Queue
from record_convert import RecordHeader, LidarData, SensorImgData, ImuData
import numpy as np
import pyqtgraph.opengl as gl
import time
from view_play_state import PlayStateEnum
import open3d as o3d
import zmq
from logger_manager import LoggerManager

class BasePubTask(QThread):
    data_ready = Signal(object, object, object)
    task_finished = Signal()
    def __init__(self):
        super().__init__()
        self._is_running = True
        self.last_ply_count = 0
        self.speed = 1.0
        self.play_state = PlayStateEnum.PAUSED
        self.logger = None

    def run(self):
        try:
            self._run_impl()
        except Exception as e:
            self.logger.error(f"线程运行错误: {e}")
        finally:
            self.task_finished.emit()

    def _run_impl(self):
        raise NotImplementedError

    def stop(self):
        self._is_running = False

    def set_play_state(self, play_state):
        self.logger.info(f'设置播放状态: {play_state}')
        self.play_state = play_state

    def set_speed(self, speed):
        self.speed = speed

class BasePlyPubTask(BasePubTask):
    def __init__(self):
        super().__init__()

    def save_point_cloud(self, points, filename):
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        self.logger.info(f'保存异常点云文件: {filename}')
        o3d.io.write_point_cloud(filename, pcd)

    def check_point_cloud_anomaly(self, points, timestamp):
        ct = len(points)
        if self.last_ply_count - ct > 1500 and self.last_ply_count > 0:
            self.logger.warning(f'点云数量异常跳变: {self.last_ply_count} -> {ct}')
            short_ts = f"{float(timestamp):.3f}"
            self.save_point_cloud(points, f'{short_ts}_{ct}.pcd')
        self.last_ply_count = ct

class BaseImgPubTask(BasePubTask):
    def __init__(self):
        super().__init__()

class ZmqService:
    def __init__(self, zmq_host: str, zmq_port: str):
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.zmq_host = zmq_host
        self.zmq_port = zmq_port
        self.context = zmq.Context()
        self.zmq_socket = None

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        if self.zmq_socket:
            self.zmq_socket.close()
            self.zmq_socket = None
        if self.context:
            self.context.term()
            self.context = None

    def connect(self):
        try:
            self.zmq_socket = self.context.socket(zmq.SUB)
            addr = f'tcp://{self.zmq_host}:{self.zmq_port}'
            self.zmq_socket.connect(addr)
            self.zmq_socket.setsockopt_string(zmq.SUBSCRIBE, '')
            self.logger.info(f'已连接到ZMQ服务器: {addr}')
        except zmq.ZMQError as e:
            self.logger.error(f'ZMQ连接错误: {e}')
            raise

    def receive_data(self) -> bytes:
        return self.zmq_socket.recv(flags=zmq.NOBLOCK)

class LocalPlyPubTask(BasePlyPubTask):
    def __init__(self, filename, speed=1.0):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.filename = filename
        self.last_timestamp = 0.0
        self.speed = speed

    def _run_impl(self):
        try:
            if self.filename and (self.filename.endswith('.pcd') or self.filename.endswith('.ply')):
                self.load_point_cloud_file(self.filename)
            elif self.filename and self.filename.endswith('.record'):
                with open(self.filename, 'rb') as f:
                    self._process_file_data(f)
            self.logger.info('结束文件数据处理')
        except FileNotFoundError:
            self.logger.error(f'文件不存在: {self.filename}')
        except Exception as e:
            self.logger.error(f'文件打开错误: {e}')

    def load_point_cloud_file(self, filename):
        pcd = o3d.io.read_point_cloud(filename)
        points = np.asarray(pcd.points)
        if len(pcd.colors) > 0:
            colors = np.asarray(pcd.colors)
        else:
            colors = np.ones_like(points) * 0.5
        colors[:, 2] = 1.0
        self.data_ready.emit(points, colors)

    def _process_file_data(self, file_handler):
        while self._is_running:
            if self.play_state == PlayStateEnum.PLAYING:
                if not self._process_single_frame(file_handler):
                    break
            elif self.play_state == PlayStateEnum.PAUSED:
                time.sleep(0.05)
            else:
                break

    def _process_single_frame(self, file_handler) -> bool:
        try:
            # 读取数据
            timestamp, _, data = RecordHeader.read_record_head_a_data(file_handler, 'lidar_data')
            if not data:
                self.logger.info('文件读取完成')
                return False

            # 处理点云数据
            points, colors, st = LidarData.get_lidar_points_np(data)

            # 帧率控制
            sleep_time = min(self.last_timestamp, timestamp - self.last_timestamp)
            time.sleep(sleep_time / self.speed)
            self.last_timestamp = timestamp

            # 发送数据并检查异常
            self.data_ready.emit(points, colors, st)
            self.check_point_cloud_anomaly(points, timestamp)
            return True
        except Exception as e:
            self.logger.error(f'数据处理错误: {e}')
            return False

class ZmqPlyPubTask(BasePlyPubTask):
    def __init__(self, zmq_host: str, zmq_port: str):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.zmq_service = ZmqService(zmq_host, zmq_port)

    def __del__(self):
        self.zmq_service.cleanup()

    def _run_impl(self):
        try:
            self.zmq_service.connect()

            while self._is_running:
                if self.play_state == PlayStateEnum.PLAYING:
                    try:
                        data = self.zmq_service.receive_data()
                        points, colors, st = LidarData.get_lidar_points_np(data)
                        self.data_ready.emit(points, colors, st)
                        self.check_point_cloud_anomaly(points, time.time())
                    except zmq.Again:
                        time.sleep(0.001)
                elif self.play_state == PlayStateEnum.PAUSED:
                    time.sleep(0.05)
                else:
                    break
            self.logger.info('结束ZMQ数据接收')
        except zmq.ZMQError as e:
            self.logger.error(f'ZMQ连接错误: {e}')
        finally:
            self.logger.info('正在清理ZMQ连接...')
            self.zmq_service.cleanup()

class ZmqImgPubTask(BaseImgPubTask):
    def __init__(self, zmq_host: str, zmq_port: str):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.zmq_service = ZmqService(zmq_host, zmq_port)

    def __del__(self):
        self.zmq_service.cleanup()

    def _run_impl(self):
        try:
            self.zmq_service.connect()

            while self._is_running:
                if self.play_state == PlayStateEnum.PLAYING:
                    try:
                        data = self.zmq_service.receive_data()
                        # 打印数据长度
                        self.logger.info(f'接收到的数据长度: {len(data)}')
                        left_img, right_img, st = SensorImgData.get_sensor_img_data(data)
                        self.data_ready.emit(right_img, 1, st)
                    except zmq.Again:
                        time.sleep(0.001)
                elif self.play_state == PlayStateEnum.PAUSED:
                    time.sleep(0.05)
                else:
                    break
            self.logger.info('结束ZMQ数据接收')
        except zmq.ZMQError as e:
            self.logger.error(f'ZMQ连接错误: {e}')
        finally:
            self.logger.info('正在清理ZMQ连接...')
            self.zmq_service.cleanup()

class LocalImgPubTask(BaseImgPubTask):
    def __init__(self, filename, speed=1.0):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.filename = filename
        self.last_timestamp = 0.0
        self.speed = speed

class LocalImuPubTask(BasePubTask):
    def __init__(self, filename):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.filename = filename
        self.last_timestamp = 0.0

    def _run_impl(self):
        try:
            with open(self.filename, 'rb') as f:
                while self._is_running:
                    if self.play_state == PlayStateEnum.PLAYING:

                        timestamp, data_size, data = RecordHeader.read_record_head_a_data(f, 'dds_imu')
                        if not data:
                            self.logger.info('文件读取完成')
                        ax, ay, az, gx, gy, gz, stamp = ImuData.get_imu_data(data)
                        acc = [ax, ay, az]
                        gyro = [gx, gy, gz]

                        # 帧率控制

                        # if self.last_timestamp > 0:
                        #     sleep_time = (stamp - self.last_timestamp) / self.speed
                        #     if sleep_time > 0:
                        #         time.sleep(sleep_time)
                        # self.last_timestamp = stamp

                        sleep_time = min(self.last_timestamp, timestamp - self.last_timestamp)
                        time.sleep(sleep_time / self.speed)
                        self.last_timestamp = timestamp

                        self.data_ready.emit(acc, gyro, stamp)
                    elif self.play_state == PlayStateEnum.PAUSED:
                        time.sleep(0.05)
                    else:
                        break
        except Exception as e:
            self.logger.error(f'IMU数据处理错误: {e}')
        finally:
            self.task_finished.emit()

class ZmqImuPubTask(BasePubTask):
    def __init__(self, zmq_host: str, zmq_port: str):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.zmq_service = ZmqService(zmq_host, zmq_port)

    def _run_impl(self):
        try:
            self.zmq_service.connect()
            while self._is_running:
                if self.play_state == PlayStateEnum.PLAYING:
                    try:
                        data = self.zmq_service.receive_data()

                        ax, ay, az, gx, gy, gz, stamp = ImuData.get_imu_data(data)
                        acc = [ax, ay, az]
                        gyro = [gx, gy, gz]
                        self.data_ready.emit(acc, gyro, stamp)
                    except zmq.Again:
                        time.sleep(0.001)
                elif self.play_state == PlayStateEnum.PAUSED:
                    time.sleep(0.05)
                else:
                    break
        except Exception as e:
            self.logger.error(f'IMU数据处理错误: {e}')
        finally:
            self.task_finished.emit()

