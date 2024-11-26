from enum import Enum
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel 
from view_play_state import PlayStateMachine, PlayingState, PausedState, TerminateState, PlayStateEnum
import pyqtgraph.opengl as gl
from thread_task import LocalPlyPubTask, ZmqPlyPubTask, LocalImgPubTask, ZmqImgPubTask
from enum import Enum
from logger_manager import LoggerManager
from typing import Dict, Optional

class DataOriginType(Enum):
    FILE = 0
    NETWORK = 1

class SensorView:
    def __init__(self):
        self.speed = 1.0
        self.speed_options = None
        self.filename = ""
        self.pub_task = None
        self.state_machine = PlayStateMachine()
        self.data_origin_type = DataOriginType.FILE
        self.ip = ""
        self.port = 0
        self.open_file_title = None
        self.open_file_filter = None
        self.logger = None
        self.view = None
        self.title = None

    def get_file_title_filter(self):
        return self.open_file_title, self.open_file_filter

    def set_speed(self, speed):
        if self.pub_task:
            self.speed = speed
            self.pub_task.set_speed(speed)

    def get_speed_options(self):
        return self.speed_options

    def get_speed(self):
        return self.speed

    def get_speed_text(self):
        if not self.speed_options:
            return ""
        for text, value in self.speed_options:
            if abs(value - self.speed) < 0.001:
                return text
        return f"{self.speed}x"

    def set_filename(self, filename):
        self.filename = filename

    def open_file(self, filename):
        if self.pub_task:
            self.terminate()
        self.filename = filename
        self.init_pub_task(DataOriginType.FILE)

    def pause(self):
        if self.pub_task:
            self.state_machine.play_control()
            self.pub_task.set_play_state(PlayStateEnum.PAUSED)
            return True
        return False

    def playing(self):
        self.logger.info('开始播放')
        if self.data_origin_type == DataOriginType.FILE:
            if not self.filename:
                self.logger.error('文件路径不正确')
                return False
        elif self.data_origin_type == DataOriginType.NETWORK:
            if not self.ip or not self.port:
                self.logger.error('网络连接信息不完整')
                return False
        else:
            self.logger.error('数据源类型不正确')
            return False
        self.logger.info('数据源信息完整，开始初始化发布任务')
        if self.pub_task is None:
            self.init_pub_task(self.data_origin_type)
        self.state_machine.play_control()
        self.pub_task.set_play_state(PlayStateEnum.PLAYING)
        return True

    def terminate(self):
        if self.pub_task:
            self.pub_task.set_play_state(PlayStateEnum.TERMINATE)
            self.pub_task.stop()
            self.pub_task.wait()
            self.pub_task = None
            self.clear_view()
            self.state_machine.end_action()
            return True
        return False

    def init_pub_task(self, data_origin_type):
        if data_origin_type == DataOriginType.FILE:
            self.load_local_file(self.filename)
            self.set_data_origin_type(DataOriginType.FILE)
        elif data_origin_type == DataOriginType.NETWORK:
            self.connect_network(self.ip, self.port)
            self.set_data_origin_type(DataOriginType.NETWORK)

    def _init_pub_task(self, task, update_func):
        self.pub_task = task
        self.pub_task.start()
        self.pub_task.data_ready.connect(update_func)
        self.pub_task.finished.connect(self.terminate)

    def set_data_origin_type(self, data_origin_type):
        self.data_origin_type = data_origin_type

    def get_current_state(self):
        return self.state_machine.state

    def start_connect_network(self, host, port):
        if self.pub_task:
            self.terminate()
        self.ip = host
        self.port = port
        self.init_pub_task(DataOriginType.NETWORK)

    def get_view(self):
        return self.view

    def get_title(self):
        return self.title

    def clear_view(self):
        raise NotImplementedError

    def connect_network(self, host, port):
        raise NotImplementedError

    def load_local_file(self, filename):
        raise NotImplementedError

class SensorPointCloudView(SensorView):
    def __init__(self):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.view = gl.GLViewWidget()
        self.grid = gl.GLGridItem()
        self.view.addItem(self.grid)
        self.open_file_title = "打开点云文件"
        self.open_file_filter = "点云文件 (*.pcd *.ply);;所有文件 (*.*)"
        self.title = "point_cloud"
        self.speed_options = [("0.5x", 0.5), ("1.0x", 1.0), ("1.5x", 1.5), ("2.0x", 2.0)]

    def load_local_file(self, filename):
        try:
            self._init_pub_task(LocalPlyPubTask(filename), self.update_point_cloud)
        except Exception as e:
            self.logger.error(f'加载本地文件失败: {e}')

    def connect_network(self, host, port):
        try:
            self._init_pub_task(ZmqPlyPubTask(host, port), self.update_point_cloud)
        except Exception as e:
            self.logger.error(f'连接网络失败: {e}')

    def clear_view(self):
        self.view.clear()
        self.view.addItem(self.grid)

    def update_point_cloud(self, points, colors):
        try:
            self.view.clear()
            self.view.addItem(self.grid)
            scatter = gl.GLScatterPlotItem(
                pos=points,
                color=colors,
                size=0.5,
                pxMode=True
            )
            self.view.addItem(scatter)

            # 调整视角
            # self.view.setCameraPosition(distance=40)
        except Exception as e:
            self.logger.error(f'绘制点云失败: {e}')

class SensorImageView(SensorView):
    def __init__(self):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.open_file_title = "打开图像文件"
        self.open_file_filter = "图像文件 (*.jpg *.png *.jpeg);;所有文件 (*.*)"
        self.view = QLabel()
        self.view.setStyleSheet("background-color: black;")
        self.title = "image"
        self.speed_options = [("0.5x", 0.5), ("1.0x", 1.0), ("1.5x", 1.5), ("2.0x", 2.0)]

    def load_local_file(self, filename):
        try:
            self._init_pub_task(LocalImgPubTask(filename), self.update_image)
        except Exception as e:
            self.logger.error(f'加载本地文件失败: {e}')

    def connect_network(self, host, port):
        try:
            self._init_pub_task(ZmqImgPubTask(host, port), self.update_image)
        except Exception as e:
            self.logger.error(f'连接网络失败: {e}')

    def clear_view(self):
        pass

    def update_image(self, img, id):
        try:
            self.view.setPixmap(QPixmap.fromImage(img))
        except Exception as e:
            self.logger.error(f'更新图像失败: {e}')

class SensorViewManager:
    def __init__(self):
        self._views: list[SensorView] = []
        self._current_view: Optional[SensorView] = None
        self._init_views()

    def _init_views(self):
        self._views = [
            SensorPointCloudView(),
            SensorImageView()
        ]
        if self._views:
            self._current_view = self._views[0]

    def get_view_names(self) -> list:
        return [view.get_title() for view in self._views]

    def switch_view(self, view_name: str) -> bool:
        if view_name not in self.get_view_names():
            return False

        if self._current_view:
            self._current_view.terminate()

        self._current_view = next((view for view in self._views if view.get_title() == view_name), None)
        return True

    def get_current_view(self) -> Optional[SensorView]:
        return self._current_view

    def terminate_all(self):
        for view in self._views:
            view.terminate()