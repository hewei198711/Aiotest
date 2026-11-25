# encoding: utf-8

import asyncio
import os
import sys
from pprint import pprint

from aiotest.cli import (
    find_aiotestfile,
    handle_error_and_exit,
    load_aiotestfile,
    parse_options,
    validate_file_exists,
)
from aiotest.distributed_coordinator import RedisConnection
from aiotest.events import events, init_events
from aiotest.logger import logger
from aiotest.runner_factory import RunnerFactory


async def main():
    """
    aiotest主入口函数

    执行流程：
    1. 解析命令行参数
    2. 配置日志系统
    3. 加载测试文件
    4. 根据参数启动对应的运行器(本地/主节点/工作节点)
    5. 运行测试并处理结果

    Raises:
        SystemExit: 在以下情况退出程序：
            - 参数验证失败
            - 测试文件加载失败
            - 测试运行被中断
    """
    # 注意：Windows 事件循环策略统一在 __main__.py 的同步入口中设置
    # （策略必须在事件循环创建前设置，asyncio.run 之后再设无效，故此处不再重复）

    # 解析命令行参数
    options = parse_options()
    # 配置日志系统
    logger.setLevel(options.loglevel)

    # 初始化redis（仅在分布式模式下）
    redis_connection = None
    redis_client = None
    if options.master or options.worker:
        redis_password = options.redis_password
        if not redis_password:
            logger.warning("Redis password not set. Use --redis-password")
            redis_password = ""
        redis_connection = RedisConnection()
        redis_client = await redis_connection.get_client(
            path=options.redis_path,
            port=options.redis_port,
            password=redis_password
        )

    # 加载测试文件
    aiotestfile = find_aiotestfile(options.aiotestfile)
    validate_file_exists(aiotestfile, "Aiotestfile")

    # 加载用户类和形状类
    user_classes, shape_instance = load_aiotestfile(aiotestfile)

    # 注册装饰器定义的处理器
    await events.register_all_pending_handlers()

    # 触发 init_events，执行用户定义的初始化回调
    await init_events.fire()

    if not user_classes:
        handle_error_and_exit(f"在文件中未找到 User 类: {aiotestfile}")
    user_classes = list(user_classes.values())

    # 检查每个用户类的 jobs 列表是否为空
    for user_class in user_classes:
        if not hasattr(user_class, 'jobs') or not user_class.jobs:
            handle_error_and_exit(
                f"在 User 类中未找到 jobs: {user_class.__name__}. "
                "任务函数必须以 'test_' 开头或以 '_test' 结尾 "
                "(例如: test_get_request, get_request_test)")

    # 检查文件描述符限制（非Windows系统）
    if os.name != "nt" and not options.master:
        try:
            import resource
            if resource.getrlimit(resource.RLIMIT_NOFILE)[0] < 10000:
                resource.setrlimit(
                    resource.RLIMIT_NOFILE, [
                        10000, resource.RLIM_INFINITY])
        except Exception:
            logger.warning(
                "系统打开文件限制低于推荐的 '10000' 设置。"
                "对于负载测试可能不够，且操作系统不允许 aiotest 自动增加。"
            )

    # 显示用户权重
    if options.show_users_weight:
        user_weight = {user.__name__: user.weight for user in user_classes}
        pprint(user_weight)
        sys.exit(0)

    # 使用局部变量替代全局变量
    runner = None
    if options.master:
        runner = await RunnerFactory.create("master", user_classes, shape_instance, options, redis_client)
        while True:
            healthy_workers = await runner.get_healthy_workers()
            if len(healthy_workers) >= options.expect_workers:
                break
            logger.info(
                "等待Worker节点准备就绪，已连接 %d/%d",
                len(healthy_workers), options.expect_workers
            )
            await asyncio.sleep(2)
    elif options.worker:
        runner = await RunnerFactory.create("worker", user_classes, shape_instance, options, redis_client)
        # Worker 必须调用 start() 来启动心跳发送和命令监听等后台任务
        await runner.start()
    else:
        runner = await RunnerFactory.create("local", user_classes, shape_instance, options)

    try:
        if not options.worker:
            # 启动测试
            await runner.start()
            # 运行测试直到完成
            await runner.run_until_complete()
            # 测试完成后,通知Worker节点退出
            await runner.quit()
            # 给Worker节点足够的时间来接收和处理quit命令
            await asyncio.sleep(3.0)
        else:
            # Worker 模式持续运行：quit 命令由命令监听器处理并置位 is_quit，
            # 这里只需轮询等待退出信号
            while not runner.state_manager.is_in_quit_state():
                await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        await runner.quit()
        # 给Worker节点足够的时间来接收和处理quit命令
        await asyncio.sleep(3)
        sys.exit(0)
    finally:
        # 关闭 Redis 连接（正常退出与 KeyboardInterrupt 路径统一在此处理）
        if redis_connection:
            await redis_connection.close()
