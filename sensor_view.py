from enum import Enum
from PySide6.QtCore import QObject, Signal, Slot
from view_play_state import PlayStateMachine, PlayingState, PausedState, TerminateState, PlayStateEnum
import pyqtgraph.opengl as gl
from thread_task import LocalPlyPubTask, ZmqPlyPubTask
from enum import Enum
from logger_manager import LoggerManager
import time

class DataOriginType(Enum):
    FILE = 0
    NETWORK = 1

class SensorView:
    def __init__(self):
        self.speed = 1.0
        self.filename = ""
        self.pub_task = None
        self.state_machine = PlayStateMachine()
        self.data_origin_type = DataOriginType.FILE
        self.ip = ""
        self.port = 0
        self.open_file_title = None
        self.open_file_filter = None
        self.logger = None

    def get_file_title_filter(self):
        return self.open_file_title, self.open_file_filter

    def set_speed(self, speed):
        if self.pub_task:
            self.speed = speed
            self.pub_task.set_speed(speed)

    def set_filename(self, filename):
        self.filename = filename

    def open_file(self, filename):
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

    def set_data_origin_type(self, data_origin_type):
        self.data_origin_type = data_origin_type

    def get_current_state(self):
        return self.state_machine.state

    def start_connect_network(self, host, port):
        self.ip = host
        self.port = port
        self.init_pub_task(DataOriginType.NETWORK)

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

    def load_local_file(self, filename):
        try:
            self._init_pub_task(LocalPlyPubTask(filename))
        except Exception as e:
            self.logger.error(f'加载本地文件失败: {e}')

    def get_view(self):
        return self.view

    def connect_network(self, host, port):
        try:
            self._init_pub_task(ZmqPlyPubTask(host, port))
        except Exception as e:
            self.logger.error(f'连接网络失败: {e}')
            
    def _init_pub_task(self, task):
        self.pub_task = task
        self.pub_task.start()
        self.pub_task.data_ready.connect(self.update_point_cloud)
        self.pub_task.finished.connect(self.terminate)

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

# 待办
# class SensorImageView(SensorView):
#     def __init__(self):
#         super().__init__()
