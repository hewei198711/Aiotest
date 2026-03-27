# encoding: utf-8

import allure
import pytest

from aiotest.state_manager import RunnerState, StateManager


@allure.feature("StateManager")
class TestStateManager:
    """StateManager 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试 StateManager 初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 StateManager 初始化时正确设置状态"""
        manager = StateManager()
        assert manager.get_current_state() == RunnerState.READY
        assert manager.is_in_quit_state() is False

    @allure.story("状态转换")
    @allure.title("测试合法状态转换")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_valid_state_transitions(self):
        """测试合法的状态转换"""
        manager = StateManager()

        # READY -> STARTING
        await manager.transition_state(RunnerState.STARTING)
        assert manager.get_current_state() == RunnerState.STARTING

        # STARTING -> RUNNING
        await manager.transition_state(RunnerState.RUNNING)
        assert manager.get_current_state() == RunnerState.RUNNING

        # RUNNING -> STOPPING
        await manager.transition_state(RunnerState.STOPPING)
        assert manager.get_current_state() == RunnerState.STOPPING

        # STOPPING -> READY
        await manager.transition_state(RunnerState.READY)
        assert manager.get_current_state() == RunnerState.READY

    @allure.story("状态转换")
    @allure.title("测试非法状态转换")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_invalid_state_transitions(self):
        """测试非法的状态转换"""
        manager = StateManager()

        # READY -> RUNNING (非法转换)
        with pytest.raises(RuntimeError):
            await manager.transition_state(RunnerState.RUNNING)

        # READY -> STOPPING (非法转换)
        with pytest.raises(RuntimeError):
            await manager.transition_state(RunnerState.STOPPING)

    @allure.story("状态转换")
    @allure.title("测试紧急停止状态转换")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_emergency_stop_transition(self):
        """测试紧急停止状态转换"""
        manager = StateManager()

        # 启动到运行状态
        await manager.transition_state(RunnerState.STARTING)
        await manager.transition_state(RunnerState.RUNNING)

        # RUNNING -> QUITTING (紧急停止)
        await manager.transition_state(RunnerState.QUITTING)
        assert manager.get_current_state() == RunnerState.QUITTING

    @allure.story("状态转换")
    @allure.title("测试相同状态转换")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_same_state_transition(self):
        """测试相同状态的转换（应该无操作）"""
        manager = StateManager()

        # 初始状态是 READY
        initial_state = manager.get_current_state()

        # 再次转换到 READY
        await manager.transition_state(RunnerState.READY)

        # 状态应该保持不变
        assert manager.get_current_state() == initial_state

    @allure.story("状态查询")
    @allure.title("测试是否可以启动")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_can_start(self):
        """测试 can_start 方法"""
        manager = StateManager()

        # READY 状态应该可以启动
        assert manager.can_start() is True

        # 启动后应该不能启动
        await manager.transition_state(RunnerState.STARTING)
        assert manager.can_start() is False

        # 运行中应该不能启动
        await manager.transition_state(RunnerState.RUNNING)
        assert manager.can_start() is False

    @allure.story("状态查询")
    @allure.title("测试是否正在运行")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_is_running(self):
        """测试 is_running 方法"""
        manager = StateManager()

        # READY 状态应该不在运行
        assert manager.is_running() is False

        # 启动中应该不在运行
        await manager.transition_state(RunnerState.STARTING)
        assert manager.is_running() is False

        # 运行中应该在运行
        await manager.transition_state(RunnerState.RUNNING)
        assert manager.is_running() is True

    @allure.story("状态查询")
    @allure.title("测试是否可以停止")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_can_stop(self):
        """测试 can_stop 方法"""
        manager = StateManager()

        # READY 状态应该不能停止
        assert manager.can_stop() is False

        # 启动中应该可以停止
        await manager.transition_state(RunnerState.STARTING)
        assert manager.can_stop() is True

        # 运行中应该可以停止
        await manager.transition_state(RunnerState.RUNNING)
        assert manager.can_stop() is True

    @allure.story("退出状态")
    @allure.title("测试设置退出状态")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_set_quit_state(self):
        """测试设置退出状态"""
        manager = StateManager()

        # 初始状态
        assert manager.is_in_quit_state() is False

        # 设置退出状态
        manager.set_quit_state()
        assert manager.is_in_quit_state() is True

        # 退出状态下状态转换应该无操作
        initial_state = manager.get_current_state()
        await manager.transition_state(RunnerState.STARTING)
        assert manager.get_current_state() == initial_state

    @allure.story("状态转换")
    @allure.title("测试 MISSING 状态转换")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_missing_state_transition(self):
        """测试 MISSING 状态的转换"""
        # 注意：这里需要先将状态设置为 MISSING，
        # 但由于 transition_state 方法的限制，我们需要通过直接修改状态来测试
        manager = StateManager()

        # 直接修改状态为 MISSING（仅用于测试）
        manager.state = RunnerState.MISSING

        # MISSING 状态只能转换到 QUITTING
        await manager.transition_state(RunnerState.QUITTING)
        assert manager.get_current_state() == RunnerState.QUITTING

    @allure.story("状态转换")
    @allure.title("测试 STOPPING 状态转换")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_stopping_state_transition(self):
        """测试 STOPPING 状态的转换"""
        manager = StateManager()

        # 启动到运行状态
        await manager.transition_state(RunnerState.STARTING)
        await manager.transition_state(RunnerState.RUNNING)

        # 转换到 STOPPING
        await manager.transition_state(RunnerState.STOPPING)
        assert manager.get_current_state() == RunnerState.STOPPING

        # STOPPING -> READY
        await manager.transition_state(RunnerState.READY)
        assert manager.get_current_state() == RunnerState.READY

    @allure.story("状态转换")
    @allure.title("测试 QUITTING 状态转换")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_quitting_state_transition(self):
        """测试 QUITTING 状态的转换"""
        manager = StateManager()

        # 转换到 QUITTING
        await manager.transition_state(RunnerState.QUITTING)
        assert manager.get_current_state() == RunnerState.QUITTING

        # QUITTING 状态不能转换到其他状态
        with pytest.raises(RuntimeError):
            await manager.transition_state(RunnerState.READY)

    @allure.story("状态转换")
    @allure.title("测试 PAUSED 状态转换")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_paused_state_transitions(self):
        """测试 PAUSED 状态的转换"""
        manager = StateManager()

        # 启动到运行状态
        await manager.transition_state(RunnerState.STARTING)
        await manager.transition_state(RunnerState.RUNNING)

        # RUNNING -> PAUSED
        await manager.transition_state(RunnerState.PAUSED)
        assert manager.get_current_state() == RunnerState.PAUSED

        # PAUSED -> RUNNING
        await manager.transition_state(RunnerState.RUNNING)
        assert manager.get_current_state() == RunnerState.RUNNING

        # 再次暂停
        await manager.transition_state(RunnerState.PAUSED)
        assert manager.get_current_state() == RunnerState.PAUSED

        # PAUSED -> STOPPING
        await manager.transition_state(RunnerState.STOPPING)
        assert manager.get_current_state() == RunnerState.STOPPING

        # STOPPING -> READY
        await manager.transition_state(RunnerState.READY)
        assert manager.get_current_state() == RunnerState.READY

    @allure.story("状态查询")
    @allure.title("测试是否可以暂停")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_can_pause(self):
        """测试 can_pause 方法"""
        manager = StateManager()

        # READY 状态应该不能暂停
        assert manager.can_pause() is False

        # 启动中应该不能暂停
        await manager.transition_state(RunnerState.STARTING)
        assert manager.can_pause() is False

        # 运行中应该可以暂停
        await manager.transition_state(RunnerState.RUNNING)
        assert manager.can_pause() is True

        # 暂停状态应该不能暂停
        await manager.transition_state(RunnerState.PAUSED)
        assert manager.can_pause() is False

    @allure.story("状态查询")
    @allure.title("测试是否可以恢复")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_can_resume(self):
        """测试 can_resume 方法"""
        manager = StateManager()

        # READY 状态应该不能恢复
        assert manager.can_resume() is False

        # 启动中应该不能恢复
        await manager.transition_state(RunnerState.STARTING)
        assert manager.can_resume() is False

        # 运行中应该不能恢复
        await manager.transition_state(RunnerState.RUNNING)
        assert manager.can_resume() is False

        # 暂停状态应该可以恢复
        await manager.transition_state(RunnerState.PAUSED)
        assert manager.can_resume() is True

    @allure.story("状态转换")
    @allure.title("测试非法暂停状态转换")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_invalid_pause_transitions(self):
        """测试非法的暂停状态转换"""
        manager = StateManager()

        # READY -> PAUSED (非法转换)
        with pytest.raises(RuntimeError):
            await manager.transition_state(RunnerState.PAUSED)

        # STARTING -> PAUSED (非法转换)
        await manager.transition_state(RunnerState.STARTING)
        with pytest.raises(RuntimeError):
            await manager.transition_state(RunnerState.PAUSED)

    @allure.story("状态转换")
    @allure.title("测试非法恢复状态转换")
    @allure.severity(allure.severity_level.NORMAL)
    async def test_invalid_resume_transitions(self):
        """测试非法的恢复状态转换"""
        manager = StateManager()

        # READY -> RUNNING (非法转换，应该先到 STARTING)
        with pytest.raises(RuntimeError):
            await manager.transition_state(RunnerState.RUNNING)

        # 启动到运行状态
        await manager.transition_state(RunnerState.STARTING)
        await manager.transition_state(RunnerState.RUNNING)

        # 启动到暂停状态
        await manager.transition_state(RunnerState.PAUSED)

        # PAUSED -> PAUSED (非法转换，应该无操作)
        # 由于 transition_state 方法会检查相同状态并直接返回，所以不会抛出异常
        await manager.transition_state(RunnerState.PAUSED)
        assert manager.get_current_state() == RunnerState.PAUSED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
