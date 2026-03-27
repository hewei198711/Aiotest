# encoding: utf-8

import asyncio
from enum import Enum

from aiotest.logger import logger


class RunnerState(Enum):
    READY = "ready"        # 就绪/已停止状态
    STARTING = "starting"  # 启动中
    RUNNING = "running"    # 运行中
    PAUSED = "paused"      # 暂停
    MISSING = "missing"    # 丢失（仅用于工作节点）
    STOPPING = "stopping"  # 停止中
    QUITTING = "quitting"  # 退出中

    def __str__(self):
        return self.value


class StateManager:
    """状态管理器，负责状态转换和状态机实现"""

    def __init__(self):
        self.state: RunnerState = RunnerState.READY
        self._state_lock: asyncio.Lock = asyncio.Lock()
        self.is_quit: bool = False

    async def transition_state(self, new_state: RunnerState) -> None:
        """
        实现状态机的安全转换，确保只有合法的状态转换才能执行。

        参数：
            new_state (RunnerState): 目标状态，必须是 RunnerState 枚举值之一。

        异常：
            RuntimeError: 当尝试非法状态转换时抛出。

        典型状态转换：
            READY -> STARTING -> RUNNING -> STOPPING -> READY
            RUNNING -> QUITTING (紧急停止)
            MISSING -> QUITTING (丢失节点只能退出)

        注意：
            - 使用状态锁保证线程安全。
            - 自动记录状态变更日志。
        """
        # 定义合法状态转换规则
        valid_transitions = {
            RunnerState.READY: [RunnerState.STARTING, RunnerState.QUITTING],
            RunnerState.STARTING: [RunnerState.RUNNING, RunnerState.STOPPING, RunnerState.QUITTING],
            RunnerState.RUNNING: [RunnerState.PAUSED, RunnerState.STOPPING, RunnerState.QUITTING],
            RunnerState.PAUSED: [RunnerState.RUNNING, RunnerState.STOPPING, RunnerState.QUITTING],
            RunnerState.MISSING: [RunnerState.QUITTING],  # 丢失状态只能退出
            RunnerState.STOPPING: [RunnerState.READY, RunnerState.QUITTING],
            RunnerState.QUITTING: []
        }

        async with self._state_lock:
            if self.is_quit or self.state == new_state:
                return
            if new_state not in valid_transitions.get(self.state, []):
                raise RuntimeError(
                    "无效的状态转换: %s -> %s", self.state, new_state)

            logger.info("状态已更改: %s -> %s", self.state, new_state)
            self.state = new_state

    def set_quit_state(self) -> None:
        """设置退出状态"""
        self.is_quit = True

    def is_in_quit_state(self) -> bool:
        """检查是否处于退出状态"""
        return self.is_quit

    def get_current_state(self) -> RunnerState:
        """获取当前状态"""
        return self.state

    def can_start(self) -> bool:
        """检查是否可以启动"""
        return self.state == RunnerState.READY

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.state == RunnerState.RUNNING

    def can_stop(self) -> bool:
        """检查是否可以停止"""
        return self.state in [RunnerState.STARTING, RunnerState.RUNNING]

    def can_pause(self) -> bool:
        """检查是否可以暂停"""
        return self.state == RunnerState.RUNNING

    def can_resume(self) -> bool:
        """检查是否可以恢复"""
        return self.state == RunnerState.PAUSED
