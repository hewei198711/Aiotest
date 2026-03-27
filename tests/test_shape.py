# encoding: utf-8

import time
from timeit import default_timer

import allure
import pytest

from aiotest.shape import LoadUserShape


# 测试用的负载形状类（在测试文件中定义，避免导入问题）
class TestLoadShape(LoadUserShape):
    """测试用的负载形状实现"""

    def tick(self):
        return (10, 1.0)


class TestLoadShapeReturnNone(LoadUserShape):
    """测试返回None的负载形状实现"""

    def tick(self):
        return None


@allure.feature("LoadUserShape")
class TestLoadUserShape:
    """LoadUserShape 类的测试用例"""

    @allure.story("初始化")
    @allure.title("测试负载形状初始化")
    @allure.severity(allure.severity_level.NORMAL)
    def test_initialization(self):
        """测试 LoadUserShape 初始化时正确设置开始时间"""
        before_init = default_timer()
        shape = TestLoadShape()
        after_init = default_timer()

        assert hasattr(shape, 'start_time')
        assert isinstance(shape.start_time, float)
        # 验证开始时间在初始化前后之间
        assert before_init <= shape.start_time <= after_init

    @allure.story("时间控制")
    @allure.title("测试重置时间功能")
    @allure.severity(allure.severity_level.NORMAL)
    def test_reset_time(self):
        """测试 reset_time 方法正确重置开始时间"""
        shape = TestLoadShape()
        original_start_time = shape.start_time

        # 等待一小段时间
        time.sleep(0.1)

        # 记录重置前的时间
        before_reset = default_timer()
        # 重置时间
        shape.reset_time()
        after_reset = default_timer()

        # 验证开始时间已更新
        assert shape.start_time > original_start_time
        # 验证新的开始时间在重置前后之间
        assert before_reset <= shape.start_time <= after_reset

    @allure.story("时间控制")
    @allure.title("测试获取运行时长")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_run_time(self):
        """测试 get_run_time 方法正确计算运行时长"""
        shape = TestLoadShape()

        # 获取初始运行时长
        initial_run_time = shape.get_run_time()
        assert initial_run_time >= 0
        assert initial_run_time < 0.1

        # 等待一小段时间
        time.sleep(0.2)

        # 再次获取运行时长
        run_time = shape.get_run_time()
        assert run_time >= 0.15  # 应该至少等待了0.15秒
        assert run_time < 0.5    # 但不超过0.5秒

    @allure.story("时间控制")
    @allure.title("测试重置时间后运行时长")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_run_time_after_reset(self):
        """测试重置时间后运行时长从0开始计算"""
        shape = TestLoadShape()

        # 等待一小段时间
        time.sleep(0.1)

        # 重置时间
        shape.reset_time()

        # 获取运行时长
        run_time = shape.get_run_time()
        assert run_time >= 0
        assert run_time < 0.1  # 重置后应该接近0

    @allure.story("抽象方法")
    @allure.title("测试 tick 方法返回用户数和速率")
    @allure.severity(allure.severity_level.NORMAL)
    def test_tick_returns_tuple(self):
        """测试 tick 方法返回正确的用户数和速率元组"""
        shape = TestLoadShape()
        result = shape.tick()

        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2

        user_count, rate = result
        assert isinstance(user_count, int)
        assert isinstance(rate, float)
        assert user_count == 10
        assert rate == 1.0

    @allure.story("抽象方法")
    @allure.title("测试 tick 方法返回 None")
    @allure.severity(allure.severity_level.NORMAL)
    def test_tick_returns_none(self):
        """测试 tick 方法可以返回 None 来停止测试"""
        shape = TestLoadShapeReturnNone()
        result = shape.tick()

        assert result is None

    @allure.story("边界情况")
    @allure.title("测试多次重置时间")
    @allure.severity(allure.severity_level.NORMAL)
    def test_multiple_reset_time(self):
        """测试多次重置时间的稳定性"""
        shape = TestLoadShape()

        for _ in range(3):
            original_time = shape.start_time
            time.sleep(0.05)
            before_reset = default_timer()
            shape.reset_time()
            after_reset = default_timer()
            assert shape.start_time > original_time
            assert before_reset <= shape.start_time <= after_reset

    @allure.story("边界情况")
    @allure.title("测试零用户和零速率")
    @allure.severity(allure.severity_level.NORMAL)
    def test_tick_zero_values(self):
        """测试 tick 方法处理零值的情况"""
        class ZeroLoadShape(LoadUserShape):
            def tick(self):
                return (0, 0.0)

        shape = ZeroLoadShape()
        result = shape.tick()

        assert result == (0, 0.0)

    @allure.story("边界情况")
    @allure.title("测试大数值")
    @allure.severity(allure.severity_level.NORMAL)
    def test_tick_large_values(self):
        """测试 tick 方法处理大数值的情况"""
        class LargeLoadShape(LoadUserShape):
            def tick(self):
                return (1000000, 9999.99)

        shape = LargeLoadShape()
        result = shape.tick()

        assert result == (1000000, 9999.99)

    @allure.story("暂停/恢复")
    @allure.title("测试暂停功能")
    @allure.severity(allure.severity_level.NORMAL)
    def test_pause(self):
        """测试暂停功能"""
        shape = TestLoadShape()

        # 暂停
        shape.pause()

        # 验证暂停状态
        assert shape.is_paused is True
        assert shape.paused_time > 0

    @allure.story("暂停/恢复")
    @allure.title("测试恢复功能")
    @allure.severity(allure.severity_level.NORMAL)
    def test_resume(self):
        """测试恢复功能"""
        shape = TestLoadShape()

        # 暂停
        shape.pause()
        assert shape.is_paused is True

        # 等待一小段时间
        time.sleep(0.1)

        # 恢复
        shape.resume()

        # 验证恢复状态
        assert shape.is_paused is False
        assert shape.pause_time > 0

    @allure.story("暂停/恢复")
    @allure.title("测试暂停期间的运行时间计算")
    @allure.severity(allure.severity_level.NORMAL)
    def test_run_time_with_pause(self):
        """测试暂停期间的运行时间计算"""
        shape = TestLoadShape()

        # 等待一小段时间
        time.sleep(0.1)

        # 记录暂停前的运行时间
        run_time_before_pause = shape.get_run_time()

        # 暂停
        shape.pause()

        # 等待一小段时间（模拟暂停期间）
        time.sleep(0.1)

        # 记录暂停期间的运行时间（应该与暂停前相同）
        run_time_during_pause = shape.get_run_time()

        # 恢复
        shape.resume()

        # 记录恢复后的运行时间
        run_time_after_resume = shape.get_run_time()

        # 验证运行时间计算正确（使用近似比较）
        assert abs(run_time_during_pause - run_time_before_pause) < 0.001
        assert run_time_after_resume > run_time_before_pause

    @allure.story("暂停/恢复")
    @allure.title("测试多次暂停/恢复")
    @allure.severity(allure.severity_level.NORMAL)
    def test_multiple_pause_resume(self):
        """测试多次暂停/恢复"""
        shape = TestLoadShape()

        # 第一次暂停
        shape.pause()
        assert shape.is_paused is True

        # 第一次恢复
        shape.resume()
        assert shape.is_paused is False
        assert shape.pause_time > 0

        # 第二次暂停
        shape.pause()
        assert shape.is_paused is True

        # 第二次恢复
        shape.resume()
        assert shape.is_paused is False
        assert shape.pause_time > 0

    @allure.story("暂停/恢复")
    @allure.title("测试重复暂停")
    @allure.severity(allure.severity_level.NORMAL)
    def test_double_pause(self):
        """测试重复暂停"""
        shape = TestLoadShape()

        # 第一次暂停
        shape.pause()
        paused_time_first = shape.paused_time
        assert shape.is_paused is True

        # 第二次暂停（应该没有效果）
        shape.pause()
        paused_time_second = shape.paused_time
        assert shape.is_paused is True
        assert paused_time_first == paused_time_second

    @allure.story("暂停/恢复")
    @allure.title("测试重复恢复")
    @allure.severity(allure.severity_level.NORMAL)
    def test_double_resume(self):
        """测试重复恢复"""
        shape = TestLoadShape()

        # 恢复（应该没有效果，因为没有暂停）
        shape.resume()
        assert shape.is_paused is False
        assert shape.pause_time == 0.0

        # 暂停
        shape.pause()
        assert shape.is_paused is True

        # 恢复
        shape.resume()
        assert shape.is_paused is False
        pause_time_first = shape.pause_time

        # 再次恢复（应该没有效果）
        shape.resume()
        assert shape.is_paused is False
        pause_time_second = shape.pause_time
        assert pause_time_first == pause_time_second

    @allure.story("暂停/恢复")
    @allure.title("测试重置时间时的暂停状态")
    @allure.severity(allure.severity_level.NORMAL)
    def test_reset_time_with_pause(self):
        """测试重置时间时的暂停状态"""
        shape = TestLoadShape()

        # 暂停
        shape.pause()
        assert shape.is_paused is True

        # 重置时间
        shape.reset_time()

        # 验证重置后的状态
        assert shape.is_paused is False
        assert shape.paused_time == 0.0
        assert shape.pause_time == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
