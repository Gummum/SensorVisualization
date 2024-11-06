import struct
import traceback
import numpy as np

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
    def get_point_data(data):
        # 读取 double timestamp (8 bytes) 和 uint8 intensity (1 byte)
        # uint16 ring (2 bytes) 和 float x, y, z (12 bytes)
        timestamp, intensity, ring, x, y, z = struct.unpack('dBxhfff', data[:24])
        return timestamp, intensity, ring, x, y, z

    @staticmethod
    def get_lidar_data(data):
        # 读取 double stamp (8 bytes) 和 uint32 height (4 bytes)
        # uint32 width (4 bytes) 和 uint8 is_dense (1 byte)
        stamp, height, width, is_dense = struct.unpack('dII?', data[:17])

        # 读取剩余数据，不拷贝，直接返回 memoryview
        data = memoryview(data[24:])

        return stamp, height, width, is_dense, data

    @staticmethod
    def get_lidar_points(points_data):
        stamp, height, width, is_dense, data = LidarData.get_lidar_data(points_data)
        points = []
        intensities = []
        for i in range(width):
            timestamp, intensity, ring, x, y, z = LidarData.get_point_data(data[i * 24:(i + 1) * 24])
            points.append([x, y, z])
            intensities.append(intensity)
        return stamp, points, intensities

    @staticmethod
    def get_lidar_points_np(points_data):
        _, points, intensities = LidarData.get_lidar_points(points_data)

        # 创建点云
        points = np.array(points)
        colors = np.ones_like(points) * 0.5
        colors[:, 2] = intensities

        return points, colors

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
