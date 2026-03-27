# encoding: utf-8

import asyncio
import os
import sys

import allure
import pytest

from aiotest.main import main

# 测试文件内容模板
test_file_content_with_users = """
from aiotest.users import User
from aiotest.shape import LoadUserShape

class TestUser(User):
    weight = 1
    async def run(self):
        pass

class TestShape(LoadUserShape):
    def tick(self):
        pass

async def on_init_redis():
    pass

init_events.add_handler(on_init_redis)
"""

test_file_content_no_users = """
from aiotest.shape import LoadUserShape

class TestShape(LoadUserShape):
    def tick(self):
        pass
"""

test_file_content_with_events = """
from aiotest.users import User
from aiotest.shape import LoadUserShape

class TestUser(User):
    weight = 1
    async def run(self):
        pass

class TestShape(LoadUserShape):
    def tick(self):
        return (1, 1)

async def on_init_events():
    pass
"""

test_file_content_with_print = """
from aiotest.users import User
from aiotest.shape import LoadUserShape

class TestUser(User):
    weight = 1
    async def run(self):
        pass

class TestShape(LoadUserShape):
    def tick(self):
        return (1, 1)

async def on_init_events():
    print("Init events called")

init_events.add_handler(on_init_events)
"""

test_file_content_no_jobs = """
from aiotest.users import User
from aiotest.shape import LoadUserShape

class TestUser(User):
    weight = 1
    # 没有以 test_ 开头或 _test 结尾的任务函数

class TestShape(LoadUserShape):
    def tick(self):
        return (1, 1)
"""

test_file_content_with_valid_jobs = """
from aiotest.users import User
from aiotest.shape import LoadUserShape

class TestUser(User):
    weight = 1

    async def test_get_request(self):
        pass

    async def test_post_request(self):
        pass

class TestShape(LoadUserShape):
    def tick(self):
        return (1, 1)
"""


@allure.feature("主函数测试")
class TestMain:
    """测试main函数"""

    @allure.story("命令行参数")
    @allure.title("测试显示用户权重选项")
    @allure.severity(allure.severity_level.NORMAL)
    def test_main_show_users_weight(self):
        """测试显示用户权重选项"""
        # 创建临时测试文件
        test_file = "test_main_show_weight.py"
        try:
            with open(test_file, 'w') as f:
                f.write(test_file_content_with_users)
            # 测试显示用户权重选项
            sys.argv = ["aiotest", "-f", test_file, "--show-users-wight"]
            with pytest.raises(SystemExit):
                asyncio.run(main())
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("命令行参数")
    @allure.title("测试无用户类的情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_main_no_user_classes(self):
        """测试无用户类的情况"""
        # 创建临时测试文件，只包含形状类
        test_file = "test_main_no_user.py"
        try:
            with open(test_file, 'w') as f:
                f.write(test_file_content_no_users)
            # 测试无用户类的情况
            sys.argv = ["aiotest", "-f", test_file]
            with pytest.raises(SystemExit):
                asyncio.run(main())
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("异常处理")
    @allure.title("测试文件不存在的情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_main_file_not_found(self):
        """测试文件不存在的情况"""
        # 测试文件不存在的情况
        sys.argv = ["aiotest", "-f", "non_existent_file.py"]
        with pytest.raises(SystemExit):
            asyncio.run(main())

    @allure.story("异常处理")
    @allure.title("测试非Python文件的情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_main_non_python_file(self):
        """测试非Python文件的情况"""
        # 创建临时非Python文件
        test_file = "test_main_non_python.txt"
        try:
            with open(test_file, 'w') as f:
                f.write("test content")
            # 测试非Python文件的情况
            sys.argv = ["aiotest", "-f", test_file]
            with pytest.raises(SystemExit):
                asyncio.run(main())
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("文件描述符限制")
    @allure.title("测试文件描述符限制检查")
    @allure.severity(allure.severity_level.NORMAL)
    def test_main_file_descriptor_limit(self):
        """测试文件描述符限制检查"""
        # 创建临时测试文件
        test_file = "test_main_fd_limit.py"
        try:
            with open(test_file, 'w') as f:
                f.write(test_file_content_with_events)
            # 测试文件描述符限制检查（通过模拟非Windows环境）
            import os
            original_os_name = os.name
            try:
                # 模拟非Windows环境
                os.name = "posix"
                # 测试文件描述符限制检查
                sys.argv = ["aiotest", "-f", test_file, "--show-users-wight"]
                with pytest.raises(SystemExit):
                    asyncio.run(main())
            finally:
                # 恢复原始环境
                os.name = original_os_name
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("初始化事件")
    @allure.title("测试初始化事件触发")
    @allure.severity(allure.severity_level.NORMAL)
    def test_main_init_events(self):
        """测试初始化事件触发"""
        # 创建临时测试文件
        test_file = "test_main_init_events.py"
        try:
            with open(test_file, 'w') as f:
                f.write(test_file_content_with_print)
            # 测试初始化事件触发
            sys.argv = ["aiotest", "-f", test_file, "--show-users-wight"]
            with pytest.raises(SystemExit):
                asyncio.run(main())
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("任务函数校验")
    @allure.title("测试用户类没有任务函数的情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_main_no_jobs(self):
        """测试用户类没有任务函数的情况"""
        # 创建临时测试文件，用户类没有以 test_ 开头或 _test 结尾的任务函数
        test_file = "test_main_no_jobs.py"
        try:
            with open(test_file, 'w') as f:
                f.write(test_file_content_no_jobs)
            # 测试用户类没有任务函数的情况
            sys.argv = ["aiotest", "-f", test_file, "--show-users-wight"]
            with pytest.raises(SystemExit):
                asyncio.run(main())
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("任务函数校验")
    @allure.title("测试用户类有有效任务函数的情况")
    @allure.severity(allure.severity_level.NORMAL)
    def test_main_with_valid_jobs(self):
        """测试用户类有有效任务函数的情况"""
        # 创建临时测试文件，用户类有以 test_ 开头的任务函数
        test_file = "test_main_with_valid_jobs.py"
        try:
            with open(test_file, 'w') as f:
                f.write(test_file_content_with_valid_jobs)
            # 测试用户类有有效任务函数的情况
            sys.argv = ["aiotest", "-f", test_file, "--show-users-wight"]
            with pytest.raises(SystemExit):
                asyncio.run(main())
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
