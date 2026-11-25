# encoding: utf-8

import asyncio
from enum import Enum
from typing import Dict, List

from aiotest.logger import logger


class RunnerState(Enum):
    READY = "ready"        # 就绪/已停止状态
    STARTING = "starting"  # 启动中
    RUNNING = "running"    # 运行中
    PAUSED = "paused"      # 暂停
    MISSING = "missing"    # 丢失（仅用于工作节点标记）
    STOPPING = "stopping"  # 停止中

    def __str__(self):
        return self.value


class StateManager:
    """状态管理器，负责状态转换和状态机实现"""

    # 合法状态转换规则（类常量）。
    # 注意：退出不走状态机——quit() 通过 set_quit_state() 置位
    # is_quit 标志实现，置位后下方守卫会早退、状态冻结。
    _VALID_TRANSITIONS: Dict[RunnerState, List[RunnerState]] = {
        RunnerState.READY: [RunnerState.STARTING],
        RunnerState.STARTING: [RunnerState.RUNNING, RunnerState.STOPPING],
        RunnerState.RUNNING: [RunnerState.PAUSED, RunnerState.STOPPING],
        RunnerState.PAUSED: [RunnerState.RUNNING, RunnerState.STOPPING],
        RunnerState.MISSING: [],  # 丢失状态无合法出边（仅作节点标记）
        RunnerState.STOPPING: [RunnerState.READY],
    }

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

        注意：
            - 退出不走状态机：quit() 通过 set_quit_state() 置位 is_quit
              标志实现，置位后所有状态转换一律早退、状态冻结。
            - 使用状态锁保证线程安全。
            - 自动记录状态变更日志。
        """
        async with self._state_lock:
            # is_quit 置位后状态机冻结：退出真相是 is_quit 标志，
            # 后续所有状态转换都会被这里吞掉
            if self.is_quit or self.state == new_state:
                return
            if new_state not in self._VALID_TRANSITIONS.get(self.state, []):
                raise RuntimeError(
                    f"无效的状态转换: {self.state} -> {new_state}")

            logger.info("状态已更改: %s -> %s", self.state, new_state)
            self.state = new_state

    def set_quit_state(self) -> None:
        """
        设置退出状态。

        退出真相是 is_quit 标志：置位后 transition_state 一律早退，
        状态机不再流转，当前状态保持冻结。
        所有退出判断应使用 is_in_quit_state()。
        """
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
        return self.state in [
            RunnerState.STARTING, RunnerState.RUNNING, RunnerState.PAUSED]

    def can_pause(self) -> bool:
        """检查是否可以暂停"""
        return self.state == RunnerState.RUNNING

    def can_resume(self) -> bool:
        """检查是否可以恢复"""
        return self.state == RunnerState.PAUSED
