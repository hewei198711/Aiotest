# encoding: utf-8

from abc import ABCMeta, abstractmethod
from timeit import default_timer
from typing import Optional, Tuple


class LoadUserShape(metaclass=ABCMeta):
    """
    负载测试形状控制的抽象基类。

    功能：
        - 定义控制负载测试形状的基本接口。
        - 子类必须实现 `tick` 方法来定义具体的负载变化规律。

    属性：
        start_time (float): 测试开始时间，用于计算运行时长。
        paused_time (float): 暂停开始的时间。
        is_paused (bool): 是否处于暂停状态。
        pause_time (float): 累计的暂停时间。

    方法：
        reset_time(): 重置开始时间。
        get_run_time(): 获取运行时长。
        pause(): 暂停计时。
        resume(): 恢复计时。
        tick(): 抽象方法，子类必须实现。

    示例：
        class MyLoadShape(LoadUserShape):
            def tick(self):
                return (100, 5.0)  # 目标用户数100，速率5.0用户/秒
    """

    def __init__(self):
        self.start_time = default_timer()
        self.paused_time = 0.0
        self.is_paused = False
        self.pause_time = 0.0

    def reset_time(self) -> None:
        """
        重置开始时间，将计时器重置为当前时间。

        功能：
            - 用于重新开始计时，通常在测试重启时调用。

        说明：
            - 调用此方法后，`get_run_time` 将重新从0开始计算运行时长。
    """
        self.start_time = default_timer()
        self.paused_time = 0.0
        self.is_paused = False
        self.pause_time = 0.0

    def get_run_time(self) -> float:
        """
        获取从开始时间到当前时间的运行时长，减去暂停的时间。

        功能：
            - 计算从 `start_time` 到当前时间的运行时长，减去累计的暂停时间。

        返回：
            float: 运行时长（秒）。

        示例：
            >>> shape = LoadUserShape()
            >>> shape.get_run_time()
            10.5  # 运行了10.5秒
    """
        if self.is_paused:
            current_time = self.paused_time
        else:
            current_time = default_timer()
        return current_time - self.start_time - self.pause_time

    def pause(self) -> None:
        """
        暂停计时，记录暂停开始的时间。

        功能：
            - 当测试暂停时，调用此方法暂停计时。
    """
        if not self.is_paused:
            self.paused_time = default_timer()
            self.is_paused = True

    def resume(self) -> None:
        """
        恢复计时，计算并累加暂停的时间。

        功能：
            - 当测试恢复时，调用此方法恢复计时，并累加暂停的时间。
    """
        if self.is_paused:
            self.pause_time += default_timer() - self.paused_time
            self.is_paused = False

    @abstractmethod
    def tick(self) -> Optional[Tuple[int, float]]:
        """
        获取当前时刻的负载控制参数，用于控制负载用户的数量变化。

        返回：
            Optional[Tuple[int, float]]:
                - 当返回一个元组 (user_count, rate) 时：
                    * user_count (int): 目标总用户数。
                    * rate (float): 每秒启动或停止的用户数。
                - 当返回 None 时：停止当前的负载测试。

        说明：
            - 这是一个抽象方法，子类必须实现此方法来定义具体的负载变化策略。
            - 通常用于动态调整负载测试的用户数量和速率。
        """
        return None
