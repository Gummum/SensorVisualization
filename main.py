import sys
import os
import numpy as np
import open3d as o3d
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QWidget, QPushButton, QFileDialog, QMenu, QLabel)
from PySide6.QtCore import QThread, Signal, QTimer, QPoint, Slot
from pyqtgraph.Qt import QtCore
import pyqtgraph.opengl as gl
from record_convert import RecordHeader, LidarData
from queue import Queue
from view_play_state import PlayingState, PausedState, TerminateState, PlayStateEnum
from network_dialog import NetworkDialog
from sensor_view import SensorPointCloudView
from logger_manager import LoggerManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.sensor_view = SensorPointCloudView()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.setWindowTitle("Sensor Visualization")
        self.setGeometry(100, 100, 800, 600)

        # 创建中心部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        central_layout = QGridLayout(central_widget)

        view_layout = QVBoxLayout()
        toolbar_layout = QHBoxLayout()

        central_layout.addLayout(toolbar_layout, 0, 0)
        central_layout.addLayout(view_layout, 1, 0)

        self.init_toolbar(toolbar_layout)
        self.init_3d_view(view_layout)

    # 初始化工具栏
    def init_toolbar(self, toolbar_layout):
        self.init_view_type_button(toolbar_layout)
        self.init_load_button(toolbar_layout)
        self.init_network_control(toolbar_layout)
        self.init_play_control(toolbar_layout)
        self.init_speed_control(toolbar_layout)

    # 添加视图类型按钮, 有点云和图像两种
    def init_view_type_button(self, toolbar_layout):
        self.view_type_button = QPushButton()
        toolbar_layout.addWidget(self.view_type_button)
        self.view_type_button.clicked.connect(self.show_view_type_menu)
        self.view_type = ["点云", "图像"]
        self.view_type_button.setText(self.view_type[0])
        self.view_menu = QMenu(self)
        for label in self.view_type:
            action = self.view_menu.addAction(label)
            action.triggered.connect(lambda checked, l=label: self.set_view_type(l))

    # 添加加载按钮
    def init_load_button(self, toolbar_layout):
        self.load_button = QPushButton("加载本地文件")
        toolbar_layout.addWidget(self.load_button)
        self.load_button.clicked.connect(self.open_local_file)

    # 初始化播放控制
    def init_play_control(self, toolbar_layout):
        self.state_text_mapping = {
            PlayingState: {"state": PlayStateEnum.PLAYING, "button": "暂停"},
            PausedState: {"state": PlayStateEnum.PAUSED, "button": "播放"},
            TerminateState: {"state": PlayStateEnum.TERMINATE, "button": "播放"}
        }
        self.init_play_button(toolbar_layout, self.sensor_view.get_current_state())
        self.init_terminte_button(toolbar_layout, self.sensor_view.get_current_state())

    # 添加播放按钮
    def init_play_button(self, toolbar_layout, state):
        self.play_button = QPushButton()
        toolbar_layout.addWidget(self.play_button)
        self.play_button.setText(self.state_text_mapping[type(state)]["button"])
        self.play_button.clicked.connect(self.view_control)

    # 添加结束按钮
    def init_terminte_button(self, toolbar_layout, state):
        self.terminte_button = QPushButton("结束")
        toolbar_layout.addWidget(self.terminte_button)
        self.terminte_button.clicked.connect(self.view_terminte)

    # 添加倍速控制
    def init_speed_control(self, toolbar_layout):
        self.speed_button = QPushButton()
        toolbar_layout.addWidget(self.speed_button)
        self.speed_button.clicked.connect(self.show_speed_menu)
        self.speed_options = [("0.5x", 0.5), ("1.0x", 1.0), ("1.5x", 1.5), ("2.0x", 2.0)]
        self.speed_button.setText(self.speed_options[1][0])
        self.speed_menu = QMenu(self)
        for label, factor in self.speed_options:
            action = self.speed_menu.addAction(label)
            action.setData(factor)
            action.triggered.connect(lambda checked, l=label, s=factor: self.set_speed(s, l))

    # 添加网络连接, 有ip地址和端口号
    def init_network_control(self, toolbar_layout):
        self.network_button = QPushButton("网络连接")
        toolbar_layout.addWidget(self.network_button)
        self.network_button.clicked.connect(self.show_network_dialog)

    # 打开本地文件
    def open_local_file(self):
        data_directory = os.path.join(os.getcwd(), "data")
        title, filter = self.sensor_view.get_file_title_filter()
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            title, 
            data_directory, 
            filter
        )
        if filename:
            self.sensor_view.open_file(filename)

    def set_view_type(self, view_type):
        self.view_type_button.setText(view_type)
    
    def show_view_type_menu(self):
        self.view_menu.exec(self.view_type_button.mapToGlobal(QPoint(0, self.view_type_button.height())))

    # 弹出网络连接对话框，输入ip地址和端口号
    def show_network_dialog(self):
        dialog = NetworkDialog()
        dialog.connect_requested.connect(self.connect_to_server)
        dialog.exec()

    def connect_to_server(self, ip_address, port):
        self.sensor_view.start_connect_network(ip_address, port)

    def init_3d_view(self, view_layout):
        view_layout.addWidget(self.sensor_view.get_view())

    def view_terminte(self):
        if self.sensor_view.terminate():
            new_state = self.sensor_view.get_current_state()
            state_text = self.state_text_mapping[type(new_state)]["button"]
            self.play_button.setText(state_text)

    def show_speed_menu(self):
        self.speed_menu.exec(self.speed_button.mapToGlobal(QPoint(0, self.speed_button.height())))

    def view_control(self):
        current_state = self.sensor_view.get_current_state().state_enum
        success = False

        if current_state == PlayStateEnum.PLAYING:
            success = self.sensor_view.pause()
        elif current_state == PlayStateEnum.PAUSED:
            success = self.sensor_view.playing()
        elif current_state == PlayStateEnum.TERMINATE:
            success = self.sensor_view.playing()

        if success:
            new_state = self.sensor_view.get_current_state()
            state_text = self.state_text_mapping[type(new_state)]["button"]
            self.play_button.setText(state_text)

    def set_speed(self, factor, text):
        self.speed_button.setText(text)
        self.sensor_view.set_speed(factor)

    def closeEvent(self, event):
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())