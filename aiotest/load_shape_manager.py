# encoding: utf-8

import asyncio
from typing import Any, Awaitable, Callable, Optional

from aiotest.logger import logger


class LoadShapeManager:
    """负载形状管理器，负责管理负载测试的形状变化逻辑"""

    def __init__(self, load_shape: Any,
                 apply_load_callback: Callable[[int, float], Awaitable[Any]]):
        """
        初始化负载形状管理器

        参数:
            load_shape: 负载形状对象，需要实现 tick() 方法，返回 (user_count, rate) 元组或 None
            apply_load_callback: 应用负载的回调函数，接收 (user_count, rate) 参数
        """
        self.load_shape = load_shape
        self.apply_load_callback = apply_load_callback
        self._task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self) -> None:
        """启动负载形状管理"""
        if self._is_running:
            logger.warning("负载形状管理器已经在运行")
            return

        if not self.load_shape:
            raise ValueError("负载形状是必需的但未提供")

        # 验证 load_shape 是否有 tick 方法
        if not hasattr(self.load_shape, "tick") or not callable(
                self.load_shape.tick):
            raise ValueError("负载形状必须有一个 tick() 方法")

        self._is_running = True
        self._task = asyncio.create_task(
            self._run_shape_test(),
            name="load_shape_manager")
        logger.info("负载形状管理器已启动")

    async def stop(self) -> None:
        """停止负载形状管理"""
        if not self._is_running:
            return

        self._is_running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("负载形状管理器已被取消")

        self._task = None
        logger.info("负载形状管理器已停止")

    async def _handle_error(self, error: Exception,
                            consecutive_errors: int) -> int:
        """
        处理错误并返回更新后的连续错误计数

        参数:
            error: 发生的错误
            consecutive_errors: 当前连续错误计数

        返回:
            更新后的连续错误计数
        """
        logger.error("形状测试错误: %s", str(error))
        consecutive_errors += 1
        if consecutive_errors > 3:
            logger.error("连续错误过多，停止形状测试")
        await asyncio.sleep(1)
        return consecutive_errors

    async def _run_shape_test(self) -> None:
        """形状测试主逻辑"""
        logger.info("形状测试正在启动")
        shape_last = None  # 上次配置
        consecutive_errors = 0  # 连续错误计数

        try:
            while self._is_running:
                try:
                    # 获取下一个形状配置
                    shape_new = self.load_shape.tick()

                    # 检查是否应该停止
                    if shape_new is None:
                        logger.info("形状测试已停止（收到None）")
                        break

                    # 检查是否与上次相同
                    if shape_last == shape_new:
                        await asyncio.sleep(1)
                        continue

                    # 解析新配置
                    try:
                        user_count, rate = shape_new
                        logger.info(
                            "负载更新: %d 个用户，速率: %.2f/s", user_count, rate)

                        # 应用新配置 - 调用回调函数
                        await self.apply_load_callback(user_count, rate)
                        shape_last = shape_new
                        consecutive_errors = 0  # 重置错误计数

                    except (ValueError, TypeError) as e:
                        consecutive_errors = await self._handle_error(e, consecutive_errors)
                        if consecutive_errors > 3:
                            break

                except Exception as e:
                    consecutive_errors = await self._handle_error(e, consecutive_errors)
                    if consecutive_errors > 3:
                        break

        except asyncio.CancelledError:
            logger.info("形状测试已被取消")

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._is_running

    @property
    def task(self) -> Optional[asyncio.Task]:
        """获取后台任务"""
        return self._task


class StandaloneLoadShapeRunner:
    """独立的负载形状运行器，用于不需要继承BaseRunner的场景"""

    def __init__(self, load_shape: Any,
                 apply_load_callback: Callable[[int, float], Awaitable[Any]]):
        """
        初始化独立负载形状运行器

        参数:
            load_shape: 负载形状对象，需要实现 tick() 方法
            apply_load_callback: 应用负载的回调函数，接收 (user_count, rate) 参数
        """
        self.load_shape_manager = LoadShapeManager(
            load_shape, apply_load_callback)
        self._quit_flag = False

    async def start(self) -> None:
        """启动形状测试"""
        if self._quit_flag:
            raise RuntimeError("退出后无法启动")

        await self.load_shape_manager.start()

    async def quit(self) -> None:
        """退出形状测试"""
        self._quit_flag = True
        await self.load_shape_manager.stop()

    @property
    def is_quit(self) -> bool:
        """检查是否已退出"""
        return self._quit_flag

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.load_shape_manager.is_running
