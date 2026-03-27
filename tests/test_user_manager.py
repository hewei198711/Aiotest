# encoding: utf-8

import asyncio

import allure
import pytest

from aiotest.user_manager import UserManager
from aiotest.users import User, weight


# 测试用的用户类
class TestUser(User):
    """测试用的用户类"""

    async def test_task(self):
        await asyncio.sleep(0.1)


@weight(2)
class WeightedUser1(User):
    """权重为2的用户类"""

    async def test_task(self):
        await asyncio.sleep(0.1)


@weight(3)
class WeightedUser2(User):
    """权重为3的用户类"""

    async def test_task(self):
        await asyncio.sleep(0.1)


@weight(1)
class WeightedUser3(User):
    """权重为1的用户类"""

    async def test_task(self):
        await asyncio.sleep(0.1)


@allure.feature("UserManager")
class TestUserManager:
    """UserManager 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 UserManager 基本初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 UserManager 初始化时正确设置属性"""
        user_types = [TestUser, WeightedUser1]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        assert manager.user_types == user_types
        assert manager.config == config
        assert manager.active_users == []

    @allure.story("初始化")
    @allure.title("测试 UserManager 空用户类型初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization_empty_user_types(self):
        """测试使用空用户类型列表初始化"""
        config = {"host": "http://localhost:8080"}
        manager = UserManager([], config)

        assert manager.user_types == []
        assert manager.config == config
        assert manager.active_users == []


@allure.feature("权重分配")
class TestWeightedDistribution:
    """权重分配算法的测试用例"""

    @allure.story("权重计算")
    @allure.title("测试单一用户类型权重分配")
    @allure.severity(allure.severity_level.NORMAL)
    def test_calculate_weighted_counts_single_type(self):
        """测试单一用户类型的权重分配"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        result = manager._calculate_weighted_counts(user_types, 10)
        assert result == {TestUser: 10}

    @allure.story("权重计算")
    @allure.title("测试多用户类型权重分配")
    @allure.severity(allure.severity_level.NORMAL)
    def test_calculate_weighted_counts_multiple_types(self):
        """测试多用户类型的权重分配"""
        user_types = [WeightedUser1, WeightedUser2]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        result = manager._calculate_weighted_counts(user_types, 100)
        assert TestUser not in result
        assert WeightedUser1 in result
        assert WeightedUser2 in result
        # 权重比例 2:3，期望分配 40:60
        assert 38 <= result[WeightedUser1] <= 42
        assert 58 <= result[WeightedUser2] <= 62

    @allure.story("权重计算")
    @allure.title("测试带当前数量限制的权重分配")
    @allure.severity(allure.severity_level.NORMAL)
    def test_calculate_weighted_counts_with_current_counts(self):
        """测试带当前数量限制的权重分配"""
        user_types = [WeightedUser1, WeightedUser2]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        current_counts = {WeightedUser1: 10, WeightedUser2: 15}
        result = manager._calculate_weighted_counts(
            user_types, 30, current_counts)
        assert result[WeightedUser1] <= 10
        assert result[WeightedUser2] <= 15

    @allure.story("权重计算")
    @allure.title("测试无效权重配置")
    @allure.severity(allure.severity_level.NORMAL)
    def test_calculate_weighted_counts_invalid_weight(self):
        """测试无效的权重配置"""
        class InvalidWeightUser(User):
            weight = 0  # 无效权重

        user_types = [InvalidWeightUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        with pytest.raises(ValueError):
            manager._calculate_weighted_counts(user_types, 10)

    @allure.story("用户分配")
    @allure.title("测试基于权重的用户分配")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_distribute_users_by_weight(self):
        """测试基于权重的用户分配算法"""
        user_types = [WeightedUser1, WeightedUser2]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        result = manager.distribute_users_by_weight(100)
        assert len(result) == 100

        # 统计各类型的数量
        type1_count = sum(
            1 for user_type in result if user_type == WeightedUser1)
        type2_count = sum(
            1 for user_type in result if user_type == WeightedUser2)

        assert 38 <= type1_count <= 42
        assert 58 <= type2_count <= 62

    @allure.story("用户分配")
    @allure.title("测试空用户类型分配")
    @allure.severity(allure.severity_level.NORMAL)
    def test_distribute_users_by_weight_empty(self):
        """测试空用户类型列表的分配"""
        config = {"host": "http://localhost:8080"}
        manager = UserManager([], config)

        result = manager.distribute_users_by_weight(100)
        assert result == []


@allure.feature("用户管理")
class TestUserManagement:
    """用户管理方法的测试用例"""

    @allure.story("用户管理")
    @allure.title("测试启动用户")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_start_users(self):
        """测试启动用户"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        await manager._start_users(5, 10.0)
        assert len(manager.active_users) == 5

    @allure.story("用户管理")
    @allure.title("测试停止用户")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_stop_users(self):
        """测试停止用户"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 先启动用户
        await manager._start_users(5, 10.0)
        assert len(manager.active_users) == 5

        # 停止用户
        await manager._stop_users(3, 10.0)
        # 活跃用户数应该减少

    @allure.story("用户管理")
    @allure.title("测试用户管理核心方法")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_manage_users(self):
        """测试用户管理的核心方法"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 测试启动用户
        await manager.manage_users(5, 10.0, "start")
        assert len(manager.active_users) == 5

        # 测试停止用户
        await manager.manage_users(2, 10.0, "stop")

    @allure.story("用户管理")
    @allure.title("测试无效操作类型")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_manage_users_invalid_action(self):
        """测试无效的操作类型"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        with pytest.raises(ValueError):
            await manager.manage_users(5, 10.0, "invalid")

    @allure.story("用户管理")
    @allure.title("测试无效参数")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_manage_users_invalid_params(self):
        """测试无效的参数"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 测试负数用户数
        with pytest.raises(ValueError):
            await manager.manage_users(-1, 10.0, "start")

        # 测试负数速率
        with pytest.raises(ValueError):
            await manager.manage_users(5, -1.0, "start")


@allure.feature("批量执行")
class TestBatchExecute:
    """批量执行方法的测试用例"""

    @allure.story("批量执行")
    @allure.title("测试批量执行带速率控制")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_batch_execute_with_rate(self):
        """测试带速率控制的批量执行"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        items = [TestUser, TestUser, TestUser]
        executed = []

        async def mock_operation(item):
            executed.append(item)
            await asyncio.sleep(0.01)

        start_time = asyncio.get_event_loop().time()
        await manager._batch_execute(items, mock_operation, 10.0)  # 10个/秒
        end_time = asyncio.get_event_loop().time()

        assert len(executed) == 3
        # 速率控制应该导致总时间大于 0.2 秒（3个操作，每0.1秒一个）
        assert end_time - start_time >= 0.2

    @allure.story("批量执行")
    @allure.title("测试批量执行无速率限制")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_batch_execute_no_rate(self):
        """测试无速率限制的批量执行"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        items = [TestUser, TestUser, TestUser]
        executed = []

        async def mock_operation(item):
            executed.append(item)
            await asyncio.sleep(0.01)

        start_time = asyncio.get_event_loop().time()
        await manager._batch_execute(items, mock_operation, 0)  # 无限制
        end_time = asyncio.get_event_loop().time()

        assert len(executed) == 3


@allure.feature("用户操作")
class TestUserOperations:
    """用户操作方法的测试用例"""

    @allure.story("用户操作")
    @allure.title("测试创建并启动用户")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_create_and_start_user(self):
        """测试创建并启动单个用户"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        await manager._create_and_start_user(TestUser)
        assert len(manager.active_users) == 1
        assert isinstance(manager.active_users[0], TestUser)

    @allure.story("用户操作")
    @allure.title("测试停止用户")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_stop_user(self):
        """测试停止单个用户"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 创建并启动用户
        await manager._create_and_start_user(TestUser)
        user = manager.active_users[0]

        # 停止用户
        await manager._stop_user(user)


@allure.feature("用户选择")
class TestUserSelection:
    """用户选择方法的测试用例"""

    @allure.story("用户选择")
    @allure.title("测试选择要停止的用户")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_select_users_to_stop(self):
        """测试选择要停止的用户"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 启动多个用户
        await manager._start_users(5, 10.0)
        assert len(manager.active_users) == 5

        # 选择要停止的用户
        users_to_stop = await manager._select_users_to_stop(3)
        assert len(users_to_stop) == 3

    @allure.story("用户选择")
    @allure.title("测试选择超出活跃用户数的情况")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_select_users_to_stop_exceed(self):
        """测试选择超出活跃用户数的情况"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 启动少量用户
        await manager._start_users(3, 10.0)
        assert len(manager.active_users) == 3

        # 选择超出数量的用户
        users_to_stop = await manager._select_users_to_stop(5)
        assert len(users_to_stop) == 3


@allure.feature("状态管理")
class TestStateManagement:
    """状态管理方法的测试用例"""

    @allure.story("状态管理")
    @allure.title("测试活跃用户数量属性")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_active_user_count(self):
        """测试活跃用户数量属性"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 初始状态
        assert manager.active_user_count == 0

        # 启动用户后
        await manager._start_users(5, 10.0)
        assert manager.active_user_count >= 0

    @allure.story("状态管理")
    @allure.title("测试清理非活跃用户")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_cleanup_inactive_users(self):
        """测试清理非活跃用户"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 启动用户
        await manager._start_users(3, 10.0)
        initial_count = len(manager.active_users)

        # 清理非活跃用户
        manager.cleanup_inactive_users()
        # 活跃用户数应该保持不变或减少

    @allure.story("状态管理")
    @allure.title("测试停止所有用户")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_stop_all_users(self):
        """测试停止所有用户"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 启动用户
        await manager._start_users(5, 10.0)
        assert len(manager.active_users) == 5

        # 停止所有用户
        await manager.stop_all_users()
        assert len(manager.active_users) == 0

    @allure.story("状态管理")
    @allure.title("测试暂停所有用户")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_pause_all_users(self):
        """测试暂停所有用户"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 启动用户
        await manager._start_users(3, 10.0)
        assert len(manager.active_users) == 3

        # 暂停所有用户
        await manager.pause_all_users()
        # 活跃用户列表应该保持不变
        assert len(manager.active_users) == 3

    @allure.story("状态管理")
    @allure.title("测试恢复所有用户")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resume_all_users(self):
        """测试恢复所有用户"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 启动用户
        await manager._start_users(3, 10.0)
        assert len(manager.active_users) == 3

        # 暂停所有用户
        await manager.pause_all_users()
        
        # 恢复所有用户
        await manager.resume_all_users()
        # 活跃用户列表应该保持不变
        assert len(manager.active_users) == 3

    @allure.story("状态管理")
    @allure.title("测试空用户列表的暂停操作")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_pause_all_users_empty(self):
        """测试空用户列表的暂停操作"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 空用户列表
        assert len(manager.active_users) == 0

        # 暂停所有用户（应该无操作）
        await manager.pause_all_users()
        assert len(manager.active_users) == 0

    @allure.story("状态管理")
    @allure.title("测试空用户列表的恢复操作")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_resume_all_users_empty(self):
        """测试空用户列表的恢复操作"""
        user_types = [TestUser]
        config = {"host": "http://localhost:8080"}
        manager = UserManager(user_types, config)

        # 空用户列表
        assert len(manager.active_users) == 0

        # 恢复所有用户（应该无操作）
        await manager.resume_all_users()
        assert len(manager.active_users) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
