import sys
import numpy as np
import open3d as o3d
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QWidget, QPushButton, QFileDialog)
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtCore

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("点云查看器")
        self.setGeometry(100, 100, 800, 600)

        # 创建中心部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建3D视图
        self.view = gl.GLViewWidget()
        layout.addWidget(self.view)

        # 添加坐标轴
        self.grid = gl.GLGridItem()
        self.view.addItem(self.grid)

        # 添加加载按钮
        self.load_button = QPushButton("加载点云文件")
        self.load_button.clicked.connect(self.load_point_cloud)
        layout.addWidget(self.load_button)

    def load_point_cloud(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "选择点云文件", 
            "", 
            "Point Cloud Files (*.pcd *.ply);;PCD files (*.pcd);;PLY files (*.ply)"
        )
        
        if filename:
            # 读取点云文件
            pcd = o3d.io.read_point_cloud(filename)
            points = np.asarray(pcd.points)
            colors = np.asarray(pcd.colors) if pcd.has_colors() else np.ones_like(points) * 0.5

            # 清除之前的点云
            self.view.clear()
            self.view.addItem(self.grid)

            # 创建散点图
            scatter = gl.GLScatterPlotItem(
                pos=points,
                color=colors,
                size=0.1,
                pxMode=False
            )
            self.view.addItem(scatter)

            # 调整视角
            self.view.setCameraPosition(distance=40)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())