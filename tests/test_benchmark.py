# encoding: utf-8
"""
Performance benchmark tests for AioTest core components.

These tests verify the performance characteristics of critical operations
and serve as regression detection for performance degradations.

Usage:
    pip install pytest-benchmark
    pytest tests/test_benchmark.py -v --benchmark-only
    pytest tests/test_benchmark.py -v --benchmark-autosave
"""

import asyncio

import allure
import pytest

pytest.importorskip("pytest_benchmark", reason="pytest-benchmark not installed")

from aiotest.metrics import RequestMetrics
from aiotest.shape import LoadUserShape
from aiotest.state_manager import RunnerState, StateManager
from aiotest.task_manager import TaskManager
from aiotest.users import WaitTimeResolver, User


class BenchmarkUser(User):
    """Minimal user for benchmarking."""
    async def test_bench(self):
        pass


@allure.feature("用户创建")
class TestBenchmarkUserCreation:
    """Benchmark user instance creation and lifecycle."""

    @allure.story("实例化")
    @allure.title("Benchmark bare User instantiation")
    @allure.severity(allure.severity_level.NORMAL)
    def test_user_instantiation(self, benchmark):
        """Benchmark bare User instantiation."""
        def create():
            return User(wait_time=1.0, weight_val=1)
        user = benchmark(create)
        assert user is not None

    @allure.story("任务检测")
    @allure.title("Benchmark User with task detection")
    @allure.severity(allure.severity_level.NORMAL)
    def test_user_with_jobs(self, benchmark):
        """Benchmark User with task detection."""
        def create():
            return BenchmarkUser(wait_time=1.0, weight_val=1)
        user = benchmark(create)
        assert len(user.jobs) >= 1

    @allure.story("生命周期")
    @allure.title("Benchmark user start/stop lifecycle")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_user_start_stop(self, benchmark):
        """Benchmark user start/stop lifecycle."""

        async def lifecycle():
            user = BenchmarkUser(wait_time=0.01, weight_val=1)
            user.start_tasks()
            await asyncio.sleep(0.01)
            await user.stop_tasks()

        benchmark(lambda: asyncio.run(lifecycle()))


@allure.feature("状态管理器")
class TestBenchmarkStateManager:
    """Benchmark state manager transitions."""

    @allure.story("状态转换")
    @allure.title("Benchmark valid state transition path")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_state_transitions(self, benchmark):
        """Benchmark valid state transition path."""
        async def transition_full():
            sm = StateManager()
            await sm.transition_state(RunnerState.STARTING)
            await sm.transition_state(RunnerState.RUNNING)
            await sm.transition_state(RunnerState.STOPPING)
            await sm.transition_state(RunnerState.READY)

        benchmark(lambda: asyncio.run(transition_full()))

    @allure.story("重复转换")
    @allure.title("Benchmark re-entrant same-state transition")
    @allure.severity(allure.severity_level.NORMAL)
    def test_duplicate_transition(self, benchmark):
        """Benchmark re-entrant same-state transition."""
        async def setup():
            sm = StateManager()
            await sm.transition_state(RunnerState.STARTING)
            return sm

        sm = asyncio.run(setup())

        async def re_enter():
            await sm.transition_state(RunnerState.STARTING)

        benchmark(lambda: asyncio.run(re_enter()))


@allure.feature("任务管理器")
class TestBenchmarkTaskManager:
    """Benchmark task management operations."""

    @allure.story("创建取消")
    @allure.title("Benchmark task creation and cancellation")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_and_cancel(self, benchmark):
        """Benchmark task creation and cancellation."""

        async def cycle():
            tm = TaskManager()
            async def dummy():
                await asyncio.sleep(0.001)
            tm.create_task(dummy(), name="bench")
            await tm.cancel_all_tasks()

        benchmark(lambda: asyncio.run(cycle()))

    @allure.story("任务计数")
    @allure.title("Benchmark active task counting")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_task_count(self, benchmark):
        """Benchmark active task counting."""
        async def setup():
            tm = TaskManager()
            for i in range(100):
                async def d():
                    pass
                tm.add_task(asyncio.ensure_future(d()))
            return tm

        tm = asyncio.run(setup())

        def count():
            return tm.get_active_task_count()

        result = benchmark(count)
        assert isinstance(result, (int, float))


@allure.feature("指标")
class TestBenchmarkMetrics:
    """Benchmark metrics dataclass operations."""

    @allure.story("创建指标")
    @allure.title("Benchmark RequestMetrics instantiation")
    @allure.severity(allure.severity_level.NORMAL)
    def test_metrics_creation(self, benchmark):
        """Benchmark RequestMetrics instantiation."""
        def create():
            return RequestMetrics(
                request_id="bench-001",
                method="GET",
                endpoint="/api/bench",
                status_code=200,
                duration=0.05,
                response_size=1024,
            )

        metrics = benchmark(create)
        assert metrics.request_id == "bench-001"

    @allure.story("错误指标")
    @allure.title("Benchmark RequestMetrics with error info")
    @allure.severity(allure.severity_level.NORMAL)
    def test_metrics_with_error(self, benchmark):
        """Benchmark RequestMetrics with error info."""
        def create():
            return RequestMetrics(
                request_id="err-001",
                method="POST",
                endpoint="/api/err",
                status_code=500,
                duration=1.5,
                error={"type": "TimeoutError", "message": "Request timed out"},
            )

        metrics = benchmark(create)
        assert metrics.error is not None


@allure.feature("等待时间解析")
class TestBenchmarkWaitTimeResolver:
    """Benchmark wait time resolution."""

    @allure.story("固定等待")
    @allure.title("Benchmark fixed wait time resolution")
    @allure.severity(allure.severity_level.NORMAL)
    def test_fixed_wait_time(self, benchmark):
        """Benchmark fixed wait time resolution."""
        async def resolve():
            return await WaitTimeResolver.resolve_wait_time(2.5)

        result = benchmark(lambda: asyncio.run(resolve()))
        assert result == 2.5

    @allure.story("范围等待")
    @allure.title("Benchmark range-based wait time resolution")
    @allure.severity(allure.severity_level.NORMAL)
    def test_range_wait_time(self, benchmark):
        """Benchmark range-based wait time resolution."""
        async def resolve():
            return await WaitTimeResolver.resolve_wait_time((1.0, 3.0))

        result = benchmark(lambda: asyncio.run(resolve()))
        assert 1.0 <= result <= 3.0


@allure.feature("负载形状")
class TestBenchmarkLoadShape:
    """Benchmark load shape tick operations."""

    @allure.story("tick 操作")
    @allure.title("Benchmark simple shape tick")
    @allure.severity(allure.severity_level.NORMAL)
    def test_shape_tick(self, benchmark):
        """Benchmark simple shape tick."""
        class SimpleShape(LoadUserShape):
            def tick(self):
                return (100, 10.0)

        shape = SimpleShape()
        result = benchmark(shape.tick)
        assert result == (100, 10.0)

    @allure.story("运行时间")
    @allure.title("Benchmark get_run_time")
    @allure.severity(allure.severity_level.NORMAL)
    def test_shape_get_run_time(self, benchmark):
        """Benchmark get_run_time."""
        class _ConcreteShape(LoadUserShape):
            def tick(self):
                return (0, 0)
        shape = _ConcreteShape()
        shape.start_time = 0.0
        shape.is_paused = False
        shape.pause_time = 0.0

        result = benchmark(shape.get_run_time)
        assert isinstance(result, (int, float))
