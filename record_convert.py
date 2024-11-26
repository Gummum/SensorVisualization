import struct
import traceback
import numpy as np
from ctypes import *
import cv2
from PySide6.QtGui import QImage

class imuMetaData(LittleEndianStructure):
    _fields_ = [
        ('temp', c_double),
        ('ax', c_double),
        ('ay', c_double),
        ('az', c_double),
        ('gx', c_double),
        ('gy', c_double),
        ('gz', c_double),
        ('stamp', c_double),
        ('id', c_uint32),
    ]

class sensorPointData(LittleEndianStructure):
    _fields_ = [
        ('timestamp', c_double),
        ('intensity', c_uint8),
        ('ring', c_int16),
        ('x', c_float),
        ('y', c_float),
        ('z', c_float)
    ]

class sensorPointCloudData(LittleEndianStructure):
    _fields_ = [
        ('stamp', c_double),
        # ('send_stamp', c_double),
        ('height', c_uint32),
        ('width', c_uint32),
        ('is_dense', c_uint8),
        ('data', sensorPointData * 30000)
    ]

HB_VIO_BUFFER_MAX_PLANES = 3
VIO_DATA_TYPE_E = c_int
buffer_state_e = c_int

class timeval(LittleEndianStructure):
    _fields_ = [
        ("tv_sec", c_uint64),
        ("tv_usec", c_uint64)
    ]

class image_info_t(LittleEndianStructure):
    _fields_ = [
        ("sensor_id", c_uint16),
        ("pipeline_id", c_uint32),
        ("frame_id", c_uint32),
        ("time_stamp", c_uint64),
        ("tv", timeval),
        ("buf_index", c_int32),
        ("img_format", c_int32),
        ("fd", c_int32 * HB_VIO_BUFFER_MAX_PLANES),
        ("size", c_uint32 * HB_VIO_BUFFER_MAX_PLANES),
        ("planeCount", c_uint32),
        ("dynamic_flag", c_uint32),
        ("water_mark_line", c_uint32),
        ("data_type", VIO_DATA_TYPE_E),
        ("state", buffer_state_e)
    ]

class address_info_t(LittleEndianStructure):
    _fields_ = [
        ("width", c_uint16),
        ("height", c_uint16),
        ("stride_size", c_uint16),
        ("addr", c_uint64 * HB_VIO_BUFFER_MAX_PLANES),
        ("paddr", c_uint64 * HB_VIO_BUFFER_MAX_PLANES)
    ]

class hb_vio_buffer_t(LittleEndianStructure):
    _fields_ = [
        ("img_info", image_info_t),
        ("img_addr", address_info_t)
    ]

class yuv_data_t(LittleEndianStructure):
    _fields_ = [
        ("y", c_byte * 307200),
        ("uv", c_byte * 153600)
    ]

class img_data_t(LittleEndianStructure):
    _fields_ = [
        ("hb_vio_buffer", hb_vio_buffer_t),
        ("yuv_data", yuv_data_t),
        ("padding", c_byte * 2048)
    ]

class shm_img_t(LittleEndianStructure):
    _fields_ = [
        ("left_img", img_data_t),
        ("right_img", img_data_t)
    ]

class RecordHeader:
    def __init__(self):
        return

    def read_record_head_a_data(file_handle, name):
        while True:
            try:
                topic_name_bytes = bytearray()
                while True:
                    byte = file_handle.read(1)
                    if not byte:
                        return None, None, None
                    if byte == b'\x00':
                        break
                    topic_name_bytes.extend(byte)
                topic_name = topic_name_bytes.decode('utf-8')

                # 读取 double st (8 bytes) 和 uint32 size (4 bytes)
                st_data = file_handle.read(12)
                if len(st_data) < 12:
                    return None, None, None
                timestamp, data_size = struct.unpack('dI', st_data)

                # 读取剩余数据，不拷贝，直接返回 memoryview
                data = memoryview(file_handle.read(data_size))

                if len(data) != data_size:
                    return None, None, None

                if name == topic_name:
                    return timestamp, data_size, data
            except Exception as e:
                traceback.print_exc()
                break


class LidarData(RecordHeader):
    def __init__(self):
        super().__init__()
        return

    @staticmethod
    def get_lidar_points(points_data):
        # 直接将内存数据转换为结构体
        cloud_data = sensorPointCloudData.from_buffer_copy(bytearray(points_data))

        points = []
        intensities = []
        for i in range(cloud_data.width):
            point = cloud_data.data[i]
            points.append([point.x, point.y, point.z])
            intensities.append(point.intensity)

        return cloud_data.stamp, points, intensities

    @staticmethod
    def get_lidar_points_np(points_data):
        _, points, intensities = LidarData.get_lidar_points(points_data)

        points = np.array(points)
        colors = np.ones_like(points) * 0.5
        colors[:, 2] = intensities

        return points, colors

class ImuData(RecordHeader):
    def __init__(self):
        super().__init__()
        return

    @staticmethod
    def get_imu_data(data):
        imu_data = imuMetaData.from_buffer_copy(bytearray(data))
        return imu_data

class SensorImgData(RecordHeader):
    def __init__(self):
        super().__init__()
        return

    @staticmethod
    def get_sensor_img_yuv_data(data):
        double_img_obj = shm_img_t.from_buffer_copy(bytearray(data))
        l_y = double_img_obj.left_img.yuv_data.y
        l_uv = double_img_obj.left_img.yuv_data.uv
        r_y = double_img_obj.right_img.yuv_data.y
        r_uv = double_img_obj.right_img.yuv_data.uv
        l_height, l_width = 480, 640
        r_height, r_width = 480, 640
        l_img = [l_y, l_uv, l_height, l_width]
        r_img = [r_y, r_uv, r_height, r_width]
        return l_img, r_img

    @staticmethod
    def get_sensor_img_data(data):
        double_img_obj = shm_img_t.from_buffer_copy(bytearray(data))
        left_img = SensorImgData.convert_img(double_img_obj.left_img.yuv_data)
        right_img = SensorImgData.convert_img(double_img_obj.right_img.yuv_data)
        return left_img, right_img

    @staticmethod
    def convert_img(data):
        yuv = np.frombuffer(data, dtype=np.uint8)
        height, width = 480, 640
        yuv_img = np.zeros((int(height * 1.5), width), dtype=np.uint8)
        yuv_img[:height] = yuv[:width * height].reshape(height, width)
        yuv_img[height:] = yuv[width * height:width * height * 3 // 2].reshape(height // 2, width)
        rgb = cv2.cvtColor(yuv_img, cv2.COLOR_YUV2RGB_NV12)
        return QImage(rgb.data, width, height, width * 3, QImage.Format_RGB888)


# 测试代码
# if __name__ == '__main__':
#     file_path = 'data/2.record'
#     with open(file_path, 'rb') as f:
#         is_running = True
#         while is_running:
#             try:
#                 timestamp, data_size, data = RecordHeader.read_record_head_a_data(f, 'lidar_data')
#                 if not data:
#                     print("到达文件尾")
#                     break
#                 print(f'Timestamp: {timestamp}' + f'Data size: {data_size}')
#                 stamp, points, intensities = LidarData.get_lidar_points(data)
#                 if not points:
#                     print("点云数据为空")
#                     continue
#                 print(f'Stamp: {stamp}' + f'Points: {len(points)}')
#             except Exception as e:
#                 traceback.print_exc()
#                 is_running = False
#                 break
