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
from thread_task import PlyPubTask, ZmqPlyPubTask
from view_play_state import PlayStateMachine, PlayingState, PausedState, TerminateState, PlayStateEnum
import zmq
from network_dialog import NetworkDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.view_recv_thread = None
        self.filename = None

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
        self.load_button.clicked.connect(self.load_point_cloud)

    def init_play_control(self, toolbar_layout):
        self.state_text_mapping = {
            PlayingState: {"state": PlayStateEnum.PLAYING, "button": "暂停"},
            PausedState: {"state": PlayStateEnum.PAUSED, "button": "播放"},
            TerminateState: {"state": PlayStateEnum.TERMINATE, "button": "播放"}
        }
        self.state_machine = PlayStateMachine()
        self.init_play_button(toolbar_layout, self.state_machine.state)
        self.init_terminte_button(toolbar_layout, self.state_machine.state)

    # 添加播放按钮
    def init_play_button(self, toolbar_layout, state):
        # 初始化播放按钮状态
        self.play_button = QPushButton()
        toolbar_layout.addWidget(self.play_button)
        self.play_button.clicked.connect(self.veiw_control)
        self.play_button.setText(self.state_text_mapping[type(state)]["button"])

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
        self.view_recv_thread = ZmqPlyPubTask(ip_address, port)
        self.view_recv_thread.start()

    def init_3d_view(self, view_layout):
        # 创建3D视图
        self.view = gl.GLViewWidget()
        view_layout.addWidget(self.view)

        # 添加坐标轴
        self.grid = gl.GLGridItem()
        self.view.addItem(self.grid)

    def view_terminte(self):
        if self.view_recv_thread:
            self.view_recv_thread.stop()
            self.view_recv_thread.wait()
            self.view_recv_thread = None
            self.state_machine.end_action()
            self.play_button.setText(self.state_text_mapping[type(self.state_machine.state)]["button"])

    def show_speed_menu(self):
        self.speed_menu.exec(self.speed_button.mapToGlobal(QPoint(0, self.speed_button.height())))

    def veiw_control(self):
        if self.filename:
            if self.view_recv_thread is None:
                self.init_pub_thread(self.filename)
            self.state_machine.play_control()
            self.play_button.setText(self.state_text_mapping[type(self.state_machine.state)]["button"])
            self.view_recv_thread.set_play_state(self.state_text_mapping[type(self.state_machine.state)]["state"].value)

    def set_speed(self, factor, text):
        self.speed_button.setText(text)
        self.view_recv_thread.set_speed(factor)

    def update_point_cloud(self, points, colors):
        try:
            # 清除之前的点云
            self.view.clear()
            self.view.addItem(self.grid)

            # 创建散点图
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
            print('Error while drawing item:')

    def load_point_cloud(self):
        data_directory = os.path.join(os.getcwd(), "data")
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "选择点云文件", 
            data_directory, 
            "record Files (*.record);;PCD files (*.pcd);;PLY files (*.ply)"
        )

        self.load_file(filename)

    def load_file(self, filename):
        if filename:
            self.filename = filename
            if filename.endswith('.record'):
                self.veiw_control()
            elif filename.endswith('.pcd') or filename.endswith('.ply'):
                self.load_point_cloud_file(filename)
        
    def load_point_cloud_file(self, filename):
        pcd = o3d.io.read_point_cloud(filename)
        points = np.asarray(pcd.points)
        if len(pcd.colors) > 0:
            colors = np.asarray(pcd.colors)
        else:
            colors = np.ones_like(points) * 0.5
        colors[:, 2] = 1.0

        self.update_point_cloud(points, colors)

    def init_pub_thread(self, filename):
        self.view_recv_thread = PlyPubTask(filename)
        self.view_recv_thread.start()
        self.view_recv_thread.data_ready.connect(self.update_point_cloud)
        self.view_recv_thread.finished.connect(self.view_terminte)

    def closeEvent(self, event):
        if self.view_recv_thread:
            self.view_recv_thread.stop()
            self.view_recv_thread.wait()
            self.view_recv_thread = None
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())