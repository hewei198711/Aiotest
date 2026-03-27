# encoding: utf-8

import asyncio

import allure
import pytest

from aiotest.load_shape_manager import (LoadShapeManager,
                                        StandaloneLoadShapeRunner)


# 测试用的负载形状类
class TestLoadShape:
    """测试用的负载形状类"""

    def __init__(self):
        self.tick_count = 0
        self.return_none = False

    def tick(self):
        """模拟负载形状的 tick 方法"""
        self.tick_count += 1
        if self.return_none and self.tick_count > 3:
            return None
        return (10 * self.tick_count, 1.0)


# 异常的负载形状类（无 tick 方法）
class InvalidLoadShape:
    """无效的负载形状类（无 tick 方法）"""
    pass


@allure.feature("LoadShapeManager")
class TestLoadShapeManager:
    """LoadShapeManager 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 LoadShapeManager 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 LoadShapeManager 初始化时正确设置属性"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        manager = LoadShapeManager(load_shape, mock_callback)

        assert manager.load_shape == load_shape
        assert manager.apply_load_callback == mock_callback
        assert manager.is_running is False
        assert manager.task is None

    @allure.story("启动")
    @allure.title("测试启动负载形状管理")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_start(self):
        """测试启动负载形状管理"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        load_shape.return_none = True  # 让 tick 方法返回 None 以停止运行
        manager = LoadShapeManager(load_shape, mock_callback)

        # 启动
        await manager.start()
        assert manager.is_running is True
        assert manager.task is not None

        # 等待一段时间让任务运行
        await asyncio.sleep(0.5)

        # 停止
        await manager.stop()

    @allure.story("启动")
    @allure.title("测试重复启动负载形状管理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_start_already_running(self):
        """测试重复启动负载形状管理"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        load_shape.return_none = True  # 让 tick 方法返回 None 以停止运行
        manager = LoadShapeManager(load_shape, mock_callback)

        # 第一次启动
        await manager.start()
        assert manager.is_running is True

        # 第二次启动（应该无操作）
        await manager.start()
        assert manager.is_running is True

        # 停止
        await manager.stop()

    @allure.story("启动")
    @allure.title("测试启动时缺少负载形状")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_start_no_load_shape(self):
        """测试启动时缺少负载形状"""
        async def mock_callback(user_count, rate):
            pass

        manager = LoadShapeManager(None, mock_callback)

        with pytest.raises(ValueError):
            await manager.start()

    @allure.story("启动")
    @allure.title("测试启动时负载形状无 tick 方法")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_start_invalid_load_shape(self):
        """测试启动时负载形状无 tick 方法"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = InvalidLoadShape()
        manager = LoadShapeManager(load_shape, mock_callback)

        with pytest.raises(ValueError):
            await manager.start()

    @allure.story("停止")
    @allure.title("测试停止负载形状管理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_stop(self):
        """测试停止负载形状管理"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        manager = LoadShapeManager(load_shape, mock_callback)

        # 启动
        await manager.start()
        assert manager.is_running is True

        # 停止
        await manager.stop()
        assert manager.is_running is False

    @allure.story("停止")
    @allure.title("测试停止未运行的负载形状管理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_stop_not_running(self):
        """测试停止未运行的负载形状管理"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        manager = LoadShapeManager(load_shape, mock_callback)

        # 停止未运行的管理器（应该无操作）
        await manager.stop()
        assert manager.is_running is False

    @allure.story("运行逻辑")
    @allure.title("测试负载形状管理器运行逻辑")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_run_shape_test(self):
        """测试负载形状管理器的运行逻辑"""
        callback_calls = []

        async def mock_callback(user_count, rate):
            callback_calls.append((user_count, rate))
            await asyncio.sleep(0.01)

        load_shape = TestLoadShape()
        load_shape.return_none = True  # 让 tick 方法返回 None 以停止运行
        manager = LoadShapeManager(load_shape, mock_callback)

        # 启动
        await manager.start()

        # 等待运行一段时间
        await asyncio.sleep(1.0)

        # 停止
        await manager.stop()

        # 检查回调是否被调用
        assert len(callback_calls) > 0

    @allure.story("运行逻辑")
    @allure.title("测试负载形状管理器错误处理")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_error_handling(self):
        """测试负载形状管理器的错误处理"""
        error_count = 0

        async def mock_callback(user_count, rate):
            nonlocal error_count
            error_count += 1
            raise Exception("Test error")

        load_shape = TestLoadShape()
        manager = LoadShapeManager(load_shape, mock_callback)

        # 启动
        await manager.start()

        # 等待运行一段时间，让错误发生
        await asyncio.sleep(1.0)

        # 停止
        await manager.stop()


@allure.feature("StandaloneLoadShapeRunner")
class TestStandaloneLoadShapeRunner:
    """StandaloneLoadShapeRunner 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 StandaloneLoadShapeRunner 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 StandaloneLoadShapeRunner 初始化时正确设置属性"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        runner = StandaloneLoadShapeRunner(load_shape, mock_callback)

        assert runner.is_quit is False
        assert runner.is_running is False

    @allure.story("启动")
    @allure.title("测试启动独立负载形状运行器")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_start(self):
        """测试启动独立负载形状运行器"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        runner = StandaloneLoadShapeRunner(load_shape, mock_callback)

        # 启动
        await runner.start()
        assert runner.is_running is True
        assert runner.is_quit is False

        # 停止
        await runner.quit()

    @allure.story("启动")
    @allure.title("测试退出后启动独立负载形状运行器")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_start_after_quit(self):
        """测试退出后启动独立负载形状运行器"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        runner = StandaloneLoadShapeRunner(load_shape, mock_callback)

        # 启动并退出
        await runner.start()
        await runner.quit()
        assert runner.is_quit is True

        # 尝试再次启动（应该失败）
        with pytest.raises(RuntimeError):
            await runner.start()

    @allure.story("退出")
    @allure.title("测试退出独立负载形状运行器")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_quit(self):
        """测试退出独立负载形状运行器"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        runner = StandaloneLoadShapeRunner(load_shape, mock_callback)

        # 启动
        await runner.start()
        assert runner.is_running is True

        # 退出
        await runner.quit()
        assert runner.is_quit is True
        assert runner.is_running is False

    @allure.story("状态查询")
    @allure.title("测试独立负载形状运行器状态查询")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_state_queries(self):
        """测试独立负载形状运行器的状态查询"""
        async def mock_callback(user_count, rate):
            pass

        load_shape = TestLoadShape()
        runner = StandaloneLoadShapeRunner(load_shape, mock_callback)

        # 初始状态
        assert runner.is_quit is False
        assert runner.is_running is False

        # 启动后
        await runner.start()
        assert runner.is_quit is False
        assert runner.is_running is True

        # 退出后
        await runner.quit()
        assert runner.is_quit is True
        assert runner.is_running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
