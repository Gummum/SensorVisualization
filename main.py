import sys
import os
import numpy as np
import open3d as o3d
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QWidget, QPushButton, QFileDialog, QMenu, QLabel, QSplitter)
from logger_manager import LoggerManager
from window_view import WindowView
import pyqtgraph as pg

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = LoggerManager.get_logger(self.__class__.__name__)
        self.setWindowTitle("Sensor Visualization")
        self.setGeometry(100, 100, 800, 600)
        pg.setConfigOptions(antialias=True)
        pg.setConfigOption('foreground', 'k')

        # 创建中心部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.central_layout = QVBoxLayout(central_widget)

        self.view_control_layout = QHBoxLayout()
        self.view_group_layout = QGridLayout()

        self.central_layout.addLayout(self.view_control_layout)
        self.central_layout.addLayout(self.view_group_layout)

        self.view: list[WindowView] = []

        self.add_group_button = QPushButton("添加视图")
        self.view_control_layout.addWidget(self.add_group_button)
        self.add_group_button.clicked.connect(lambda: self.add_window_view(self.view_group_layout))

        self.remove_group_button = QPushButton("删除视图")
        self.view_control_layout.addWidget(self.remove_group_button)
        self.remove_group_button.clicked.connect(lambda: self.remove_window_view(self.view_group_layout))

        self.add_window_view(self.view_group_layout)

    def add_window_view(self, central_layout):
        window_view = WindowView(self)
        self.view.append(window_view)

        row = (len(self.view) - 1) // 2  # 每行最多放两个视图
        col = (len(self.view) - 1) % 2   # 列位置
        central_layout.addWidget(window_view.get_widget(), row, col)

        # 调整布局，使视图均匀分布
        self.adjust_layout(central_layout)

    def remove_window_view(self, central_layout):
        if len(self.view) == 0:
            return

        window_view = self.view.pop()
        widget = window_view.get_widget()

        widget.setParent(None)
        central_layout.removeWidget(widget)

        # 调整布局，使视图均匀分布
        self.adjust_layout(central_layout)

    def adjust_layout(self, central_layout):
        # 禁用布局更新
        central_layout.setEnabled(False)

        # 重置所有行和列的拉伸因子
        for i in range(central_layout.rowCount()):
            central_layout.setRowStretch(i, 0)
        for j in range(central_layout.columnCount()):
            central_layout.setColumnStretch(j, 0)

        rows = (len(self.view) + 1) // 2
        cols = 2 if len(self.view) > 1 else 1

        for i in range(rows):
            central_layout.setRowStretch(i, 1)
        for j in range(cols):
            central_layout.setColumnStretch(j, 1)

        # 启用布局更新
        central_layout.setEnabled(True)

    def closeEvent(self, event):
        event.accept()
        for view in self.view:
            view.closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())