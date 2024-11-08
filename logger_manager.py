import logging
import os
from datetime import datetime

class LoggerManager:
    _loggers = {}  # 用于存储所有创建的logger实例
    
    @classmethod
    def get_logger(cls, name: str, log_dir: str = "logs") -> logging.Logger:
        """
        获取或创建一个命名的logger
        
        Args:
            name: logger的名称
            log_dir: 日志文件存储目录，默认为'logs'
            
        Returns:
            logging.Logger: 配置好的logger实例
        """
        # 如果logger已存在，直接返回
        if name in cls._loggers:
            return cls._loggers[name]
            
        # 创建logger
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
        
        # 生成日志文件名（包含日期）
        log_file = os.path.join(
            log_dir, 
            f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - [%(levelname)s] - %(filename)s:%(lineno)d - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        # 清除已有的处理器（避免重复）
        logger.handlers.clear()
        
        # 添加处理器到logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        # 存储logger实例
        cls._loggers[name] = logger
        
        return logger
