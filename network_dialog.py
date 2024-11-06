from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QWidget, QPushButton, QFileDialog, QMenu, QLabel)
class NetworkDialog(QDialog):

    connect_requested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Connection")

        # IP地址输入
        ip_label = QLabel("IP:")
        self.ip_input = QLineEdit(self)
        self.ip_input.setText("192.168.2.10")

        # 端口号输入
        port_label = QLabel("Port:")
        self.port_input = QLineEdit(self)
        self.port_input.setText("12345")

        # 按钮布局
        connect_button = QPushButton("Connect")
        connect_button.clicked.connect(self.on_connect)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        # 设置布局
        layout = QVBoxLayout()
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_input)
        layout.addLayout(ip_layout)

        port_layout = QHBoxLayout()
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        layout.addLayout(port_layout)

        button_layout = QHBoxLayout()
        button_layout.addWidget(connect_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def on_connect(self):
        ip_address = self.ip_input.text()
        try:
            port = int(self.port_input.text())
            self.connect_requested.emit(ip_address, port)
            self.accept()
        except ValueError:
            print("Invalid port number")

# 示例调用
# if __name__ == "__main__":

#     app = QApplication([])
#     dialog = NetworkDialog()
    
#     def handle_connect(ip, port):
#         print(f"Attempting to connect to {ip}:{port}")

#     dialog.connect_requested.connect(handle_connect)
#     dialog.exec()
