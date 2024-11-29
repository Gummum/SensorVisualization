from enum import Enum
from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout
from view_play_state import PlayStateMachine, PlayingState, PausedState, TerminateState, PlayStateEnum
import pyqtgraph.opengl as gl
from thread_task import LocalPlyPubTask, ZmqPlyPubTask, LocalImgPubTask, ZmqImgPubTask, LocalImuPubTask, ZmqImuPubTask
from enum import Enum
from logger_manager import LoggerManager
from typing import Dict, Optional
import pyqtgraph as pg
import time

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
        self.terminate_cb = None

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

    def terminate_cb_register(self, cb):
        self.terminate_cb = cb

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

    def sig_task_finished_func(self):
        if self.terminate_cb:
            self.terminate_cb()

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
        self.pub_task.task_finished.connect(self.sig_task_finished_func)

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
        # self.view.clear()
        # self.view.addItem(self.grid)
        pass

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

class SensorImuView(SensorView):
    def __init__(self):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)

        # 创建主视图容器
        self.view = QWidget()
        self.view.setContentsMargins(0, 0, 0, 0)
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.view.setLayout(self.layout)

        # 创建两个图表分别显示线性加速度和角速度
        self.acc_plot = self._create_plot("线性加速度 (m/s²)", ['x轴', 'y轴', 'z轴'])
        self.gyro_plot = self._create_plot("角速度 (rad/s)", ['x轴', 'y轴', 'z轴'])
        
        self.layout.addWidget(self.acc_plot)
        self.layout.addWidget(self.gyro_plot)

        # 数据缓存
        self.timestamps = []
        self.acc_data = [[], [], []]  # x, y, z
        self.gyro_data = [[], [], []]  # x, y, z

        # 更新计数器
        self.update_counter = 0
        self.max_update_counter = 10

        # 设置显示的时间范围（例如最近10秒的数据）
        self.display_time_range = 5  # 单位：秒

        # 自动范围调整标志位
        self.auto_range_enabled = True

        # 定时器
        self.auto_range_timer = QTimer()
        self.auto_range_timer.setSingleShot(True)
        self.auto_range_timer.timeout.connect(self.auto_range_enable)

        # 视图配置
        self.open_file_title = "打开IMU数据文件"
        self.open_file_filter = "IMU数据文件 (*.record);;所有文件 (*.*)"
        self.title = "imu"
        self.speed_options = [("0.5x", 0.5), ("1.0x", 1.0), ("1.5x", 1.5), ("2.0x", 2.0)]

        self.acc_plot.getPlotItem().vb.sigRangeChangedManually.connect(self.auto_range_disable)
        self.gyro_plot.getPlotItem().vb.sigRangeChangedManually.connect(self.auto_range_disable)

    def _create_plot(self, title, labels):
        plot = pg.PlotWidget(title=title)
        plot.setBackground('w')  # 设置背景颜色为白色
        plot.addLegend() # 添加图例
        plot.showGrid(x=True, y=True) # 显示网格
        plot.setLabel('left', title) # 设置左侧标签为 title
        plot.setLabel('bottom', '时间 (s)')  # 设置底部标签为 '时间 (ms)'

        # 设置三个轴的颜色
        colors = ['#FF0000', '#00FF00', '#0000FF']  # 红绿蓝
        for label, color in zip(labels, colors):
            plot.plot([], [], pen=pg.mkPen(color=color, width=2), name=label) # 添加三个曲线
        return plot

    def load_local_file(self, filename):
        try:
            self._init_pub_task(LocalImuPubTask(filename), self.update_imu_data)
        except Exception as e:
            self.logger.error(f'加载本地文件失败: {e}')

    def connect_network(self, host, port):
        try:
            self._init_pub_task(ZmqImuPubTask(host, port), self.update_imu_data)
        except Exception as e:
            self.logger.error(f'连接网络失败: {e}')

    def clear_view(self):
        self.timestamps.clear()
        for data_list in [self.acc_data, self.gyro_data]:
            for sublist in data_list:
                sublist.clear()

    def auto_range_enable(self):
        self.auto_range_enabled = True

    def auto_range_disable(self, event):
        print(self.auto_range_enabled)
        self.auto_range_enabled = False
        self.auto_range_timer.start(3000)

    def update_imu_data(self, acc, gyro):
        try:
            timestamp = time.time()
            # 如果是第一个数据点，将时间戳归零
            if not self.timestamps:
                self.time_offset = timestamp

            # 更新数据缓存
            self.timestamps.append(timestamp - self.time_offset)
            for i in range(3):
                self.acc_data[i].append(acc[i])
                self.gyro_data[i].append(gyro[i])

            self.update_counter += 1
            # 每收到 10 次数据更新一次图表
            if self.update_counter >= self.max_update_counter:
                self._update_plots()
                self.update_counter = 0  # 重置计数器
        except Exception as e:
            self.logger.error(f'更新IMU数据失败: {e}')

    def _update_plots(self):
        try:
            for i, plot_item in enumerate(self.acc_plot.listDataItems()):
                plot_item.setData(self.timestamps, self.acc_data[i])

            for i, plot_item in enumerate(self.gyro_plot.listDataItems()):
                plot_item.setData(self.timestamps, self.gyro_data[i])

            # 设置x轴显示范围为最近的 display_time_range 秒
            if self.timestamps and self.auto_range_enabled:
                self.acc_plot.setXRange(max(self.timestamps[-1] - self.display_time_range, 0), self.timestamps[-1])
                self.gyro_plot.setXRange(max(self.timestamps[-1] - self.display_time_range, 0), self.timestamps[-1])
                self.acc_plot.enableAutoRange(axis='y')
                self.gyro_plot.enableAutoRange(axis='y')

        except Exception as e:
            self.logger.error(f'更新图表失败: {e}')

class SensorViewManager:
    def __init__(self):
        self._views: list[SensorView] = []
        self._current_view: Optional[SensorView] = None
        self._init_views()

    def _init_views(self):
        self._views = [
            SensorPointCloudView(),
            SensorImageView(),
            SensorImuView()
        ]
        if self._views:
            self._current_view = self._views[0]

    def set_teriminate_cb(self, cb):
        for view in self._views:
            view.terminate_cb_register(cb)

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

# 代办事项
# 1. imu的数据显示使用的时间戳是有问题的。