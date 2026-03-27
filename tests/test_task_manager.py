# encoding: utf-8

import asyncio

import allure
import pytest

from aiotest.task_manager import TaskManager


@allure.feature("TaskManager")
class TestTaskManager:
    """TaskManager 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 TaskManager 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 TaskManager 初始化时正确设置属性"""
        manager = TaskManager()
        assert manager.background_tasks == []

    @allure.story("任务管理")
    @allure.title("测试添加单个任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_add_task(self):
        """测试添加单个后台任务"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.1)
            return "test"

        task = asyncio.create_task(test_coro())
        manager.add_task(task)

        assert len(manager.background_tasks) == 1
        assert task in manager.background_tasks

    @allure.story("任务管理")
    @allure.title("测试批量添加任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_add_tasks(self):
        """测试批量添加后台任务"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.1)
            return "test"

        tasks = [asyncio.create_task(test_coro()) for _ in range(3)]
        manager.add_tasks(tasks)

        assert len(manager.background_tasks) == 3
        for task in tasks:
            assert task in manager.background_tasks

    @allure.story("任务管理")
    @allure.title("测试创建任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_create_task(self):
        """测试创建并添加后台任务"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.1)
            return "test"

        task = manager.create_task(test_coro(), name="test_task")

        assert len(manager.background_tasks) == 1
        assert task in manager.background_tasks
        assert task.get_name() == "test_task"

    @allure.story("任务管理")
    @allure.title("测试取消所有任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_cancel_all_tasks(self):
        """测试取消所有后台任务"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.5)
            return "test"

        # 添加多个任务
        for _ in range(3):
            manager.create_task(test_coro())

        assert len(manager.background_tasks) == 3

        # 取消所有任务
        await manager.cancel_all_tasks()

        # 检查任务是否被清理
        for task in manager.background_tasks:
            assert task.done()

    @allure.story("任务管理")
    @allure.title("测试根据名称获取任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_get_task_by_name(self):
        """测试根据名称获取任务"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.1)
            return "test"

        # 创建带名称的任务
        task1 = manager.create_task(test_coro(), name="task1")
        task2 = manager.create_task(test_coro(), name="task2")

        # 测试获取存在的任务
        found_task = manager.get_task_by_name("task1")
        assert found_task == task1

        # 测试获取不存在的任务
        not_found_task = manager.get_task_by_name("task3")
        assert not_found_task is None

    @allure.story("任务管理")
    @allure.title("测试移除任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_remove_task(self):
        """测试移除任务"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.1)
            return "test"

        task = manager.create_task(test_coro())
        assert len(manager.background_tasks) == 1

        # 移除任务
        manager.remove_task(task)
        assert len(manager.background_tasks) == 0
        assert task not in manager.background_tasks

    @allure.story("任务管理")
    @allure.title("测试清理已完成的任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_clear_completed_tasks(self):
        """测试清理已完成的任务"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.1)
            return "test"

        # 创建任务并等待完成
        task1 = manager.create_task(test_coro())
        await task1

        # 创建未完成的任务
        task2 = manager.create_task(asyncio.sleep(0.5))

        assert len(manager.background_tasks) == 2

        # 清理已完成的任务
        manager.clear_completed_tasks()
        assert len(manager.background_tasks) == 1
        assert task2 in manager.background_tasks

    @allure.story("任务管理")
    @allure.title("测试获取活跃任务数量")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_get_active_task_count(self):
        """测试获取活跃任务数量"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.1)
            return "test"

        # 初始状态
        assert manager.get_active_task_count() == 0

        # 添加任务后
        for _ in range(3):
            manager.create_task(test_coro())
        assert manager.get_active_task_count() == 3

        # 等待任务完成后
        await asyncio.sleep(0.2)
        manager.clear_completed_tasks()
        assert manager.get_active_task_count() == 0

    @allure.story("任务管理")
    @allure.title("测试等待任务完成")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_wait_for_task_completion(self):
        """测试等待所有任务完成"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.2)
            return "test"

        # 添加任务
        for _ in range(2):
            manager.create_task(test_coro())

        # 等待任务完成
        start_time = asyncio.get_event_loop().time()
        await manager.wait_for_task_completion()
        end_time = asyncio.get_event_loop().time()

        # 确保任务已完成
        for task in manager.background_tasks:
            assert task.done()
        # 确保等待时间合理（允许一定误差）
        assert end_time - start_time >= 0.15

    @allure.story("任务管理")
    @allure.title("测试等待任务完成超时")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_wait_for_task_completion_timeout(self):
        """测试等待任务完成超时"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.5)
            return "test"

        # 添加任务
        manager.create_task(test_coro())

        # 等待任务完成（超时）
        start_time = asyncio.get_event_loop().time()
        await manager.wait_for_task_completion(timeout=0.1)
        end_time = asyncio.get_event_loop().time()

        # 确保等待时间接近超时时间（允许一定误差）
        assert 0.08 <= end_time - start_time <= 0.25

    @allure.story("任务管理")
    @allure.title("测试根据名称停止任务")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_stop_task_by_name(self):
        """测试根据名称停止任务"""
        manager = TaskManager()

        async def test_coro():
            await asyncio.sleep(0.5)
            return "test"

        # 创建带名称的任务
        manager.create_task(test_coro(), name="test_task")

        # 停止任务
        result = await manager.stop_task_by_name("test_task")
        assert result is True

        # 测试停止不存在的任务
        result = await manager.stop_task_by_name("non_existent")
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
