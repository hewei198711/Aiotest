# encoding: utf-8

import argparse
import inspect
import os
import sys
from functools import lru_cache
from typing import Dict, Optional, Tuple, Type

# 检查Python版本
if sys.version_info < (3, 9):
    print("错误: AioTest 需要 Python 3.9 或更高版本。")
    print(f"您正在使用 Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys.exit(1)

from aiotest.logger import logger
from aiotest.shape import LoadUserShape
from aiotest.users import User

version = "1.0.7"


def parse_options(args=None):
    """
    解析命令行参数并返回解析结果。

    功能：
        - 解析命令行参数，支持分布式测试模式配置。
        - 提供基础参数、Redis参数、分布式参数、日志参数等分组。

    参数：
        args (list|None): 要解析的参数列表，默认为None表示使用sys.argv。

    返回：
        argparse.Namespace: 解析后的参数对象。

    异常：
        argparse.ArgumentError: 如果参数解析失败。
    """

    # Initialize
    parser = argparse.ArgumentParser(
        prog="aiotest [options]",
        description="aiotest是一个易于使用、可脚本化且可扩展的性能测试工具"
    )

    # 参数分组
    group_distributed = parser.add_argument_group('分布式模式参数')
    group_redis = parser.add_argument_group('Redis参数')
    group_prometheus = parser.add_argument_group('Prometheus参数')
    group_metrics = parser.add_argument_group('Metrics 配置')
    group_logging = parser.add_argument_group('日志参数')

    # 基础参数
    parser.add_argument(
        '-f', '--aiotestfile',
        default='aiotestfile',
        help="要导入的Python模块文件，例如：'../other.py'。默认值：aiotestfile"
    )

    parser.add_argument(
        '-H', '--host',
        default="",
        help="要进行负载测试的主机，格式如下：http://10.21.32.33"
    )

    # show
    parser.add_argument(
        '--show-users-wight',
        action='store_true',
        help="打印用户类执行权重的JSON数据"
    )

    parser.add_argument(
        '-V', '--version',
        action='version',
        version='%(prog)s {}'.format(version),
    )

    # Redis参数
    group_redis.add_argument(
        '--redis-path',
        default="127.0.0.1",
        help="Redis服务器地址"
    )

    group_redis.add_argument(
        '--redis-port',
        type=int,
        default=6379,
        help="Redis服务器端口"
    )

    group_redis.add_argument(
        '--redis-password',
        default="123456",
        help="Redis服务器密码"
    )

    # 分布式参数
    group_distributed.add_argument(
        '--master',
        action='store_true',
        help="设置aiotest以分布式模式运行，此进程作为主节点"
    )

    group_distributed.add_argument(
        '--worker',
        action='store_true',
        help="设置aiotest以分布式模式运行，此进程作为工作节点"
    )

    group_distributed.add_argument(
        '--expect-workers',
        type=int,
        default=1,
        help="主节点在开始测试前期望连接的工作节点数量"
    )

    # loglevel logfile
    group_logging.add_argument(
        '--loglevel', '-L',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help="日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL, 默认=INFO)",
    )

    group_logging.add_argument(
        '--logfile',
        default=None,
        help="日志文件路径。如果未设置，日志将输出到stdout/stderr",
    )

    group_prometheus.add_argument(
        '--prometheus-port',
        type=int,
        default=8089,
        help="Prometheus指标服务器端口 (默认: 8089)",
    )

    group_metrics.add_argument(
        '--metrics-collection-interval',
        type=float,
        default=5.0,
        help="指标收集间隔（秒） (默认: 5.0)",
    )

    group_metrics.add_argument(
        '--metrics-batch-size',
        type=int,
        default=100,
        help="指标批处理大小 (默认: 100)",
    )

    group_metrics.add_argument(
        '--metrics-flush-interval',
        type=float,
        default=1.0,
        help="指标刷新间隔（秒） (默认: 1.0)",
    )

    group_metrics.add_argument(
        '--metrics-buffer-size',
        type=int,
        default=10000,
        help="指标缓冲区大小 (默认: 10000)",
    )

    return parser.parse_args(args=args)


def handle_error_and_exit(message, error=None):
    """
    处理错误并退出程序

    功能：
        - 记录错误信息
        - 如果提供了错误对象，记录详细的错误信息
        - 退出程序

    参数：
        message (str): 错误消息
        error (Exception, optional): 错误对象
    """
    if error:
        logger.error("%s: %s", message, error)
    else:
        logger.error(message)
    sys.exit(1)


def validate_file_exists(file_path, file_type):
    """
    验证文件是否存在

    功能：
        - 检查文件是否存在
        - 如果不存在，记录错误并退出

    参数：
        file_path (str): 文件路径
        file_type (str): 文件类型描述

    返回：
        bool: 如果文件存在，返回True
    """
    if not file_path:
        handle_error_and_exit(
            f"未找到任何 {file_type}！确保文件以'.py'结尾并查看--help获取可用选项。")
    return True


@lru_cache(maxsize=32)
def find_aiotestfile(aiotestfile):
    """
    查找并验证aiotest测试文件路径。

    功能：
        - 检查文件扩展名是否为.py。
        - 处理包含目录的路径和用户目录标记（如~/）。
        - 返回文件的绝对路径。

    参数：
        aiotestfile (str): 测试文件名或路径。

    返回：
        str|None: 返回找到的绝对路径，未找到时返回None。

    异常：
        SystemExit: 当文件扩展名不是.py或文件不存在时退出程序。
    """

    # 分割文件名和扩展名
    _, suffix = os.path.splitext(aiotestfile)

    # 检查扩展名是否为.py
    if suffix and suffix != ".py":
        handle_error_and_exit(f"{aiotestfile} 必须是一个.py文件")

    # 如果无扩展名，补全.py
    if not suffix:
        aiotestfile += ".py"

    # 处理包含目录的路径
    if os.path.dirname(aiotestfile):
        # 扩展用户目录标记（如 ~/）
        expanded = os.path.expanduser(aiotestfile)
        # 检查文件是否存在
        if os.path.exists(expanded):
            return os.path.abspath(expanded)
    else:
        # 处理当前目录下的文件
        path = os.path.abspath(".")
        joined = os.path.join(path, aiotestfile)
        if os.path.exists(joined):
            return os.path.abspath(joined)

    # 文件未找到时记录警告
    logger.warning(
        "当前工作目录: %s, 文件未找到: %s", os.path.abspath('.'), aiotestfile)
    return None


def is_subclass_with_prefix(
        cls, base_class, required_attrs=None, module_name=None):
    """
    检查类是否为特定基类的子类

    功能：
        - 验证类是否为指定基类的子类
        - 确保类实现了必要的属性
        - 检查类是否来自指定模块

    参数：
        cls (type): 要检查的类对象
        base_class (type): 基类
        required_attrs (list): 必需的属性列表
        module_name (str): 模块名

    返回：
        bool: 如果类是有效的子类，返回True；否则返回False
    """
    # 检查是否为类对象
    is_valid_class = inspect.isclass(cls)
    if not is_valid_class:
        return False

    try:
        # 检查是否为指定基类的子类
        is_subclass = issubclass(cls, base_class)
    except TypeError:
        # 如果 cls 不是类或类型对象，issubclass 会抛出 TypeError
        return False

    # 检查必需的属性
    if required_attrs:
        for attr in required_attrs:
            if not hasattr(cls, attr):
                return False

    # 检查模块名
    if module_name:
        is_from_module = cls.__module__ == module_name
        return is_subclass and not is_from_module
    else:
        return is_subclass


def is_shape_class(cls):
    """
    检查类是否为有效的LoadUserShape子类。

    功能：
        - 验证类是否为LoadUserShape的子类。
        - 确保类实现了必要的抽象方法。

    参数：
        cls (type): 要检查的类对象。

    返回：
        bool: 如果类是有效的LoadUserShape子类，返回True；否则返回False。
    """
    return is_subclass_with_prefix(
        cls, LoadUserShape, module_name="aiotest.shape")


def is_user_class(cls):
    """
    检查类是否为有效的User子类

    Args:
        cls (type): 要检查的类对象

    Returns:
        bool: 如果是有效的User子类返回True，否则返回False
    """
    return is_subclass_with_prefix(cls, User, required_attrs=[
                                   "weight"], module_name="aiotest.users")


def load_aiotestfile(
        path: str) -> Tuple[Dict[str, Type[User]], Optional[LoadUserShape]]:
    """
    加载aiotest测试文件并提取用户类和形状类

    Args:
        path (str): 测试文件路径

    Returns:
        tuple: 包含两个元素的元组：
            - dict: 用户类字典 {类名: 类对象}
            - LoadUserShape: 形状类实例(如果存在)

    Raises:
        SystemExit: 当文件加载失败或没有找到用户类时退出程序
    """
    import importlib.util

    # 确保路径是绝对路径
    path = os.path.abspath(path)

    # 分离目录和文件名
    directory, aiotestfile = os.path.split(path)
    module_name = os.path.splitext(aiotestfile)[0]

    try:
        # 使用 importlib.util 直接从文件路径导入模块
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None:
            handle_error_and_exit(
                f"从文件创建模块规范失败: {path}")

        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
    except Exception as e:
        handle_error_and_exit(f"加载模块失败: {module_name}", e)

    # 提取用户类
    user_classes = {
        name: cls
        for name, cls in vars(imported).items()
        if is_user_class(cls)
    }

    # 提取形状类
    shape_classes = [
        cls
        for cls in vars(imported).values()
        if is_shape_class(cls)
    ]

    # 检查形状类数量（必须且只能有一个）
    shape_instance = None
    if len(shape_classes) == 1:
        shape_instance = shape_classes[0]()
    elif len(shape_classes) == 0:
        handle_error_and_exit(
            "测试文件中需要一个 LoadUserShape 类!")
    else:
        handle_error_and_exit(
            "测试文件中只允许有一个 LoadUserShape 类!")

    return user_classes, shape_instance
