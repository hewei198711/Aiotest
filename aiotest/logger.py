# encoding: utf-8

import logging
import os
import sys
from logging import Formatter


class ExtraFieldFormatter(Formatter):
    """
    根据 extra 字段是否存在使用不同格式的日志格式化器。

    功能：
        - 动态切换日志格式，基于 extra 字段的内容。
        - 支持自定义字段的格式化规则。

    参数：
        default_fmt (str): 默认日志格式。
        field_fmt_dict (dict): 字段名与对应格式的字典。
    """

    def __init__(self, default_fmt, field_fmt_dict):
        """
        :param default_fmt: 默认格式
        :param field_fmt_dict: 字典，{字段名: 对应的格式}
        """
        super().__init__(default_fmt)
        self.default_fmt = default_fmt
        self.field_fmt_dict = field_fmt_dict

    def format(self, record):
        # 保存原始格式
        original_fmt = self._style._fmt
        try:
            # 检查每个字段是否存在
            for field, fmt in self.field_fmt_dict.items():
                if hasattr(record, field):
                    self._style._fmt = fmt
                    break
            else:
                self._style._fmt = self.default_fmt

            return super().format(record)
        finally:
            # 恢复原始格式
            self._style._fmt = original_fmt


class Logger:
    def __init__(self, name='aiotest_log', log_dir='logs', log_level='INFO'):
        """
        初始化日志记录器。

        功能：
            - 创建日志目录（如果不存在）。
            - 配置日志处理器和格式化器。

        参数：
            name (str): 日志名称。
            log_dir (str): 日志目录路径。
            log_level (str, 可选): 日志等级，默认为 INFO。
        """
        self.name = name
        self.log_dir = log_dir
        self.log_level = log_level.upper()
        os.makedirs(self.log_dir, exist_ok=True)
        self._setup_logging()

    def _setup_logging(self):
        """
        配置日志处理器和格式化器。

        功能：
            - 设置文件处理器（直接覆盖原有文件）。
            - 设置标准输出处理器。
            - 防止重复添加处理器。
        """
        self.logger = logging.getLogger(self.name)

        # 防止重复添加处理器
        if self.logger.handlers:
            # 如果已经有处理器，更新日志级别
            self.logger.setLevel(self.log_level)
            return

        # 确保日志记录器的 propagate 设置为 False，避免父记录器重复处理
        self.logger.propagate = False

        # 设置日志级别
        self.logger.setLevel(self.log_level)

        # 格式化器
        formatter = ExtraFieldFormatter(
            default_fmt='%(asctime)s | %(levelname)8s | %(filename)s:%(lineno)d | %(message)s',
            field_fmt_dict={
                'request_start': '%(asctime)s | %(levelname)8s | %(message)s | %(request_start)s',
                'response_data': '%(asctime)s | %(levelname)8s | %(message)s | %(response_data)s',
                'request_failed': '%(asctime)s | %(levelname)8s | %(message)s | %(request_failed)s',
            }
        )

        # 文件处理器 - 直接覆盖原有文件
        file_handler = logging.FileHandler(
            filename=os.path.join(self.log_dir, f'{self.name}.log'),
            mode='a',  # 追加模式
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)

        # 标准输出处理器
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)

        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(stdout_handler)

    def setLevel(self, level):
        """动态设置日志级别"""
        self.logger.setLevel(level.upper())

    def set_level(self, level):
        """动态设置日志级别（setLevel的别名）"""
        self.setLevel(level)

    def debug(self, message, *args, **kwargs):
        """记录DEBUG级别日志"""
        self.logger.debug(message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        """记录INFO级别日志"""
        self.logger.info(message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        """记录WARNING级别日志"""
        self.logger.warning(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        """记录ERROR级别日志"""
        self.logger.error(message, *args, **kwargs)

    def critical(self, message, *args, **kwargs):
        """记录CRITICAL级别日志"""
        self.logger.critical(message, *args, **kwargs)

    def get_logger(self):
        return self.logger


logger = Logger().get_logger()
