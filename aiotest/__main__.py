# encoding: utf-8

import sys

# 检查Python版本
if sys.version_info < (3, 9):
    print("错误: AioTest 需要 Python 3.9 或更高版本。")
    print(f"您正在使用 Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys.exit(1)

from aiotest.main import main

if __name__ == "__main__":
    import asyncio

    # 设置 WindowsSelectorEventLoopPolicy 以解决 zmq 兼容性问题
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
