# encoding: utf-8

import asyncio
from typing import List

from aiotest.logger import logger


class TaskManager:
    """任务管理器，负责后台任务的创建、管理和清理"""

    def __init__(self):
        self.background_tasks: List[asyncio.Task] = []

    def add_task(self, task: asyncio.Task) -> None:
        """添加后台任务"""
        self.background_tasks.append(task)

    def add_tasks(self, tasks: List[asyncio.Task]) -> None:
        """批量添加后台任务"""
        self.background_tasks.extend(tasks)

    def create_task(self, coro, name: str = None) -> asyncio.Task:
        """创建并添加后台任务"""
        task = asyncio.create_task(coro, name=name)
        self.add_task(task)
        return task

    async def cancel_all_tasks(self) -> None:
        """取消所有后台任务"""
        # 筛选需要取消的任务（排除当前任务）
        tasks_to_cancel: List[asyncio.Task] = [
            t for t in self.background_tasks
            if not t.done() and t != asyncio.current_task()
        ]

        for task in tasks_to_cancel:
            task.cancel()

        if tasks_to_cancel:
            # 等待所有取消操作完成
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            # 清理已完成的任务
            self.background_tasks = [
                t for t in self.background_tasks if not t.done()]

    def get_task_by_name(self, name: str) -> asyncio.Task:
        """根据名称获取任务"""
        for task in self.background_tasks:
            if task.get_name() == name:
                return task
        return None

    def remove_task(self, task: asyncio.Task) -> None:
        """移除任务"""
        if task in self.background_tasks:
            self.background_tasks.remove(task)

    def clear_completed_tasks(self) -> None:
        """清理已完成的任务"""
        self.background_tasks = [
            t for t in self.background_tasks if not t.done()]

    def get_active_task_count(self) -> int:
        """获取活跃任务数量"""
        return len([t for t in self.background_tasks if not t.done()])

    async def wait_for_task_completion(self, timeout: float = None) -> None:
        """等待所有任务完成"""
        if not self.background_tasks:
            return

        try:
            await asyncio.wait_for(
                asyncio.gather(*self.background_tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("任务完成超时，已超过 %d 秒", timeout)

    async def stop_task_by_name(self, name: str) -> bool:
        """根据名称停止任务"""
        task = self.get_task_by_name(name)
        if task and not task.done():
            task.cancel()
            try:
                await task
                return True
            except asyncio.CancelledError:
                return True
        return False
