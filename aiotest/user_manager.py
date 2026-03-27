# encoding: utf-8

import asyncio
from typing import Any, Callable, Dict, List, Optional, Type

from aiotest.logger import logger
from aiotest.users import User


class UserManager:
    """用户管理器，负责用户创建、启动、停止和权重分配"""

    def __init__(self, user_types: List[Type['User']], config: Dict[str, Any]):
        self.user_types: List[Type['User']] = user_types
        self.config: Dict[str, Any] = config
        self.active_users: List['User'] = []

    def _calculate_weighted_counts(
        self,
        user_types: List[Type['User']],
        target_count: int,
        current_counts: Optional[Dict[Type['User'], int]] = None
    ) -> Dict[Type['User'], int]:
        """
        通用的权重分配算法。

        参数：
            user_types (List[Type['User']]): 用户类型列表
            target_count (int): 目标分配总数
            current_counts (Optional[Dict[Type['User'], int]]): 当前各类型的用户数量（用于限制）

        返回：
            Dict[Type['User'], int]: 各用户类型到分配数量的字典

        异常：
            ValueError: 权重配置无效时抛出
        """
        if not user_types:
            return {}

        # 验证并获取权重
        weights: List[int] = []
        for user_type in user_types:
            weight = getattr(user_type, 'weight', 1)
            if not isinstance(weight, int) or weight < 1:
                raise ValueError(
                    f"用户类 {user_type.__name__} 必须有一个 'weight' 属性（整数 ≥ 1）")
            weights.append(weight)

        # 单一用户类型直接返回
        if len(user_types) == 1:
            user_type = user_types[0]
            if current_counts is not None:
                count = min(target_count, current_counts.get(user_type, 0))
            else:
                count = target_count
            return {user_type: count}

        # 计算权重总和
        total_weight = sum(weights)
        if total_weight == 0:
            return {}

        # 按权重比例计算分配数量
        counts: List[int] = []
        for user_type, weight in zip(user_types, weights):
            ratio = weight / total_weight
            count = int(round(ratio * target_count))

            # 如果有当前数量限制，确保不超过
            if current_counts is not None:
                count = min(count, current_counts.get(user_type, 0))
            count = max(count, 0)
            counts.append(count)

        # 处理舍入误差
        while sum(counts) != target_count:
            if sum(counts) < target_count:
                # 优先增加当前数量最多的类型
                if current_counts is not None:
                    idx = max(range(len(counts)),
                              key=lambda i: current_counts[user_types[i]])
                else:
                    idx = counts.index(min(counts))

                if current_counts is None or counts[idx] < current_counts[user_types[idx]]:
                    counts[idx] += 1
                else:
                    break
            else:
                # 优先减少数量最多的类型
                idx = max(range(len(counts)), key=lambda i: counts[i])
                if counts[idx] > 0:
                    counts[idx] -= 1
                else:
                    break

        return {user_type: counts[i] for i, user_type in enumerate(user_types)}

    def distribute_users_by_weight(
            self, user_count: int) -> List[Type['User']]:
        """
        基于权重的用户分配算法。

        参数：
            user_count (int): 目标用户总数。

        返回：
            List[Type['User']]: 按权重分配后的用户类列表。

        异常：
            ValueError: 权重配置无效时抛出。

        示例：
            # 假设有两个用户类：MyUser1(weight=2), MyUser2(weight=3)，目标100个用户
            # 分配结果：MyUser1 -> 40个 (2/5 * 100)，MyUser2 -> 60个 (3/5 * 100)
            user_manager = UserManager([MyUser1, MyUser2], {})
            result = user_manager.distribute_users_by_weight(100)
            # 返回: [MyUser1, MyUser1, ..., MyUser2, MyUser2, ...] (40个MyUser1, 60个MyUser2)
        """
        if not self.user_types:
            return []

        # 使用通用权重分配算法
        counts = self._calculate_weighted_counts(self.user_types, user_count)

        # 生成用户类列表
        result = []
        for user_type, count in counts.items():
            result.extend([user_type for _ in range(count)])
        return result

    async def manage_users(
        self,
        user_count: int,
        rate: float,
        action: str
    ) -> None:
        """
        用户管理的核心方法（支持平滑启停）

        参数:
            user_count: 目标用户数
            rate: 操作速率(个/秒)
            action: 操作类型('start'或'stop')

        异常:
            ValueError: 非法操作类型或参数值时抛出
        """
        # 验证参数
        if not isinstance(user_count, int) or user_count < 0:
            raise ValueError("user_count 必须是一个非负整数")
        if not isinstance(rate, (int, float)) or rate < 0:
            raise ValueError("rate 必须是一个非负数")

        if action == "start":
            await self._start_users(user_count, rate)
        elif action == "stop":
            await self._stop_users(user_count, rate)
        else:
            raise ValueError("action 必须是 'start' 或 'stop'")

    async def _start_users(self, user_count: int, rate: float):
        """启动指定数量的用户（按权重分配）"""
        user_classes = self.distribute_users_by_weight(user_count)
        await self._batch_execute(user_classes, self._create_and_start_user, rate)

    async def _stop_users(self, user_count: int, rate: float):
        """停止指定数量的用户（按权重比例）"""
        target_users = await self._select_users_to_stop(user_count)
        await self._batch_execute(target_users, self._stop_user, rate)

    async def _batch_execute(
            self, items: List, operation: Callable, rate: float):
        """
        批量操作执行器，支持速率控制

        参数：
            items (List): 需要处理的项目列表
            operation (Callable): 执行的异步操作函数
            rate (float): 操作速率（个/秒），0表示无限制

        示例：
            # rate=5.0时，每0.2秒处理一个项目
            # 10个项目预计耗时：1.8秒（最后一个不延迟）
            await _batch_execute([user1, user2], start_user, 5.0)
            # 执行顺序：start_user(user1) -> sleep(0.2) -> start_user(user2)

        逻辑说明：
            1. 计算操作间隔：delay = 1.0 / rate
               - rate=5.0 -> delay=0.2秒
               - rate=0 -> delay=0（无限制）
            2. 顺序处理每个项目：
               - 执行操作并统计成功数
               - 操作间按速率延迟（最后一个操作不延迟）
               - 捕获单个操作异常，不影响其他操作
            3. 记录处理结果（成功时记录debug日志）
        """
        success_count = 0
        delay = 1.0 / rate if rate > 0 else 0

        for i, item in enumerate(items):
            try:
                await operation(item)
                success_count += 1

                # 速率控制：最后一个操作后不需要延迟
                if i < len(items) - 1 and delay > 0:
                    await asyncio.sleep(delay)
            except Exception as e:
                logger.warning("操作失败，项目 %d: %s", i, e)
                continue

        if success_count > 0:
            logger.debug(
                "成功处理 %d/%d 个项目", success_count, len(items))

    async def _create_and_start_user(self, user_class: Type['User']):
        """创建并启动单个用户"""
        new_user: 'User' = user_class()
        # 设置 host（如果用户类需要）
        # 兼容字典和 Namespace 对象
        if hasattr(self.config, 'host'):
            # 处理 Namespace 对象
            host = getattr(self.config, 'host', None)
        else:
            # 处理字典对象
            host = self.config.get('host', None)
        if host and hasattr(new_user, 'host'):
            new_user.host = host

        new_user.start_tasks()
        self.active_users.append(new_user)

    async def _stop_user(self, user: 'User'):
        """终止单个用户"""
        if user.tasks is not None and not user.tasks.done():
            await user.stop_tasks()

    async def _select_users_to_stop(self, user_count: int):
        """
        选择要停止的用户（按权重比例）

        参数：
            user_count (int): 需要停止的用户数量

        返回：
            List['User']: 需要停止的用户实例列表

        示例：
            # 当前状态：MyUser1(weight=2): 40个, MyUser2(weight=3): 60个, 总计100个
            # 目标停止30个用户
            result = await _select_users_to_stop(30)
            # 返回：包含30个用户的列表，其中MyUser1约12个，MyUser2约18个
            # 停止后剩余：MyUser1约28个，MyUser2约42个，保持2:3的权重比例

        逻辑说明：
            1. 获取所有活跃用户（tasks未完成的）
            2. 如果停止数量≥活跃数量，返回所有活跃用户
            3. 按用户类型分组，统计各类型数量
            4. 单一用户类型时，按启动顺序停止
            5. 多用户类型：
               - 计算当前各类型数量
               - 计算停止后的目标总用户数
               - 调用权重分配算法计算各类型应停止数量
               - 按启动顺序选择要停止的用户
        """
        active_users = [
            user for user in self.active_users if user.tasks is not None and not user.tasks.done()]

        if user_count >= len(active_users):
            return active_users

        # 按用户类型分组
        users_by_type: Dict[Type['User'], List['User']] = {}
        for user in active_users:
            user_type = type(user)
            if user_type not in users_by_type:
                users_by_type[user_type] = []
            users_by_type[user_type].append(user)

        # 如果只有一种用户类型，按启动顺序停止
        if len(users_by_type) == 1:
            return active_users[:user_count]

        # 计算当前各类型数量
        current_counts = {
            user_type: len(users) for user_type,
            users in users_by_type.items()}
        user_types = list(current_counts.keys())

        # 直接使用权重分配算法计算各类型应停止的数量
        stop_counts = self._calculate_weighted_counts(
            user_types, user_count, current_counts)

        # 按启动顺序选择要停止的用户
        users_to_stop = []
        for user_type, stop_count in stop_counts.items():
            if stop_count > 0:
                users_to_stop.extend(users_by_type[user_type][:stop_count])

        return users_to_stop

    @property
    def active_user_count(self) -> int:
        """返回当前活跃用户数量"""
        return sum(
            1 for user in self.active_users if user.tasks is not None and not user.tasks.done())

    def cleanup_inactive_users(self):
        """清理非活跃用户实例（已完成的任务）"""
        self.active_users = [
            user for user in self.active_users if user.tasks is not None and not user.tasks.done()]

    async def stop_all_users(self):
        """停止所有用户"""
        for user in self.active_users:
            if not user.tasks.done():
                await user.stop_tasks()
        self.active_users.clear()

    async def pause_all_users(self):
        """暂停所有用户"""
        for user in self.active_users:
            if not user.tasks.done():
                await user.pause_tasks()

    async def resume_all_users(self):
        """恢复所有用户"""
        for user in self.active_users:
            if not user.tasks.done():
                await user.resume_tasks()
