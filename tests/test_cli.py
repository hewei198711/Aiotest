# encoding: utf-8

import os

import allure
import pytest

from aiotest.cli import (find_aiotestfile, handle_error_and_exit,
                         is_shape_class, is_subclass_with_prefix,
                         is_user_class, load_aiotestfile, parse_options,
                         validate_file_exists)
from aiotest.shape import LoadUserShape
from aiotest.users import User


@allure.feature("命令行参数解析")
class TestParseOptions:
    """测试命令行参数解析功能"""

    @allure.story("参数解析")
    @allure.title("测试解析默认参数")
    @allure.severity(allure.severity_level.NORMAL)
    def test_parse_options_default(self):
        """测试解析默认参数"""
        options = parse_options([])
        assert options.aiotestfile == "aiotestfile"
        assert options.host == ""
        assert options.redis_path == "127.0.0.1"
        assert options.redis_port == 6379
        assert options.redis_password == "123456"
        assert options.master is False
        assert options.worker is False
        assert options.expect_workers == 1
        assert options.loglevel == "INFO"
        assert options.logfile is None
        assert options.prometheus_port == 8089
        assert options.metrics_collection_interval == 5.0
        assert options.metrics_batch_size == 100
        assert options.metrics_flush_interval == 1.0
        assert options.metrics_buffer_size == 10000

    @allure.story("参数解析")
    @allure.title("测试解析自定义参数")
    @allure.severity(allure.severity_level.NORMAL)
    def test_parse_options_custom(self):
        """测试解析自定义参数"""
        args = [
            "-f", "test_file.py",
            "-H", "http://localhost:8080",
            "--redis-path", "192.168.1.1",
            "--redis-port", "6380",
            "--redis-password", "password123",
            "--master",
            "--expect-workers", "3",
            "--loglevel", "DEBUG",
            "--logfile", "test.log",
            "--prometheus-port", "8090",
            "--metrics-collection-interval", "10.0",
            "--metrics-batch-size", "200",
            "--metrics-flush-interval", "2.0",
            "--metrics-buffer-size", "20000"
        ]
        options = parse_options(args)
        assert options.aiotestfile == "test_file.py"
        assert options.host == "http://localhost:8080"
        assert options.redis_path == "192.168.1.1"
        assert options.redis_port == 6380
        assert options.redis_password == "password123"
        assert options.master is True
        assert options.worker is False
        assert options.expect_workers == 3
        assert options.loglevel == "DEBUG"
        assert options.logfile == "test.log"
        assert options.prometheus_port == 8090
        assert options.metrics_collection_interval == 10.0
        assert options.metrics_batch_size == 200
        assert options.metrics_flush_interval == 2.0
        assert options.metrics_buffer_size == 20000


@allure.feature("错误处理")
class TestErrorHandling:
    """测试错误处理功能"""

    @allure.story("错误处理")
    @allure.title("测试处理错误并退出")
    @allure.severity(allure.severity_level.NORMAL)
    def test_handle_error_and_exit(self):
        """测试处理错误并退出"""
        with pytest.raises(SystemExit):
            handle_error_and_exit("Test error")

    @allure.story("错误处理")
    @allure.title("测试处理带异常的错误并退出")
    @allure.severity(allure.severity_level.NORMAL)
    def test_handle_error_and_exit_with_exception(self):
        """测试处理带异常的错误并退出"""
        test_error = Exception("Test exception")
        with pytest.raises(SystemExit):
            handle_error_and_exit("Test error", test_error)

    @allure.story("文件验证")
    @allure.title("测试验证文件存在")
    @allure.severity(allure.severity_level.NORMAL)
    def test_validate_file_exists(self):
        """测试验证文件存在"""
        assert validate_file_exists("test_file.py", "test file") is True

    @allure.story("文件验证")
    @allure.title("测试验证文件不存在")
    @allure.severity(allure.severity_level.NORMAL)
    def test_validate_file_exists_none(self):
        """测试验证文件不存在"""
        with pytest.raises(SystemExit):
            validate_file_exists(None, "test file")


@allure.feature("文件查找")
class TestFindAiotestfile:
    """测试查找 aiotest 文件功能"""

    @allure.story("文件查找")
    @allure.title("测试查找当前目录下的文件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_find_aiotestfile_current_dir(self):
        """测试查找当前目录下的文件"""
        # 创建临时测试文件
        test_file = "test_aiotestfile.py"
        try:
            with open(test_file, 'w') as f:
                f.write("# Test file")
            # 测试查找文件
            result = find_aiotestfile(test_file)
            assert result is not None
            assert os.path.exists(result)
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("文件查找")
    @allure.title("测试查找带路径的文件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_find_aiotestfile_with_path(self):
        """测试查找带路径的文件"""
        # 创建临时测试目录和文件
        test_dir = "test_dir"
        test_file = os.path.join(test_dir, "test_aiotestfile.py")
        try:
            os.makedirs(test_dir, exist_ok=True)
            with open(test_file, 'w') as f:
                f.write("# Test file")
            # 测试查找文件
            result = find_aiotestfile(test_file)
            assert result is not None
            assert os.path.exists(result)
        finally:
            # 清理临时文件和目录
            if os.path.exists(test_file):
                os.remove(test_file)
            if os.path.exists(test_dir):
                os.rmdir(test_dir)

    @allure.story("文件查找")
    @allure.title("测试查找无扩展名的文件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_find_aiotestfile_no_extension(self):
        """测试查找无扩展名的文件"""
        # 创建临时测试文件
        test_file = "test_aiotestfile.py"
        try:
            with open(test_file, 'w') as f:
                f.write("# Test file")
            # 测试查找文件（不带扩展名）
            result = find_aiotestfile("test_aiotestfile")
            assert result is not None
            assert os.path.exists(result)
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("文件查找")
    @allure.title("测试查找不存在的文件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_find_aiotestfile_not_found(self):
        """测试查找不存在的文件"""
        result = find_aiotestfile("non_existent_file.py")
        assert result is None

    @allure.story("文件查找")
    @allure.title("测试查找非Python文件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_find_aiotestfile_non_python(self):
        """测试查找非Python文件"""
        with pytest.raises(SystemExit):
            find_aiotestfile("test_file.txt")


@allure.feature("类检查")
class TestClassChecks:
    """测试类检查功能"""

    @allure.story("类检查")
    @allure.title("测试检查有效的用户类")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_user_class_valid(self):
        """测试检查有效的用户类"""
        # 创建有效的用户类
        class TestUser(User):
            weight = 1

            async def run(self):
                pass
        assert is_user_class(TestUser) is True

    @allure.story("类检查")
    @allure.title("测试检查无效的用户类")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_user_class_invalid(self):
        """测试检查无效的用户类"""
        # 测试不是User的子类
        class NotAUser:
            pass
        assert is_user_class(NotAUser) is False

        # 测试非类对象
        assert is_user_class("not a class") is False
        assert is_user_class(None) is False

    @allure.story("类检查")
    @allure.title("测试检查有效的形状类")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_shape_class_valid(self):
        """测试检查有效的形状类"""
        # 创建有效的形状类
        class TestShape(LoadUserShape):
            def tick(self):
                pass
        assert is_shape_class(TestShape) is True

    @allure.story("类检查")
    @allure.title("测试检查无效的形状类")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_shape_class_invalid(self):
        """测试检查无效的形状类"""
        # 创建普通类
        class NotAShape:
            pass
        assert is_shape_class(NotAShape) is False

    @allure.story("类检查")
    @allure.title("测试检查子类")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_subclass_with_prefix(self):
        """测试检查子类"""
        # 创建有效的子类
        class TestSubclass(User):
            weight = 1

            async def run(self):
                pass
        assert is_subclass_with_prefix(
            TestSubclass, User, required_attrs=["weight"]) is True

        # 创建另一个有效的子类（类名不以Test开头或结尾）
        class MySubclass(User):
            weight = 1

            async def run(self):
                pass
        assert is_subclass_with_prefix(
            MySubclass, User, required_attrs=["weight"]) is True

    @allure.story("类检查")
    @allure.title("测试检查非类对象")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_subclass_with_prefix_non_class(self):
        """测试检查非类对象"""
        # 测试非类对象
        assert is_subclass_with_prefix(
            "not a class", User, required_attrs=["weight"]) is False
        assert is_subclass_with_prefix(
            123, User, required_attrs=["weight"]) is False
        assert is_subclass_with_prefix(
            None, User, required_attrs=["weight"]) is False

    @allure.story("类检查")
    @allure.title("测试检查TypeError异常")
    @allure.severity(allure.severity_level.NORMAL)
    def test_is_subclass_with_prefix_type_error(self):
        """测试检查TypeError异常"""
        # 测试会引发TypeError的情况
        assert is_subclass_with_prefix(
            object(), User, required_attrs=["weight"]) is False


@allure.feature("文件加载")
class TestLoadAiotestfile:
    """测试加载 aiotest 文件功能"""

    @allure.story("文件加载")
    @allure.title("测试加载有效的测试文件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_load_aiotestfile_valid(self):
        """测试加载有效的测试文件"""
        # 创建临时测试文件
        test_file = "test_load_file.py"
        try:
            with open(test_file, 'w') as f:
                f.write("""
from aiotest.users import User
from aiotest.shape import LoadUserShape

class TestUser(User):
    weight = 1
    async def run(self):
        pass

class TestShape(LoadUserShape):
    def tick(self):
        pass

async def init_events():
    pass
""")
            # 测试加载文件
            user_classes, shape_instance = load_aiotestfile(test_file)
            assert len(user_classes) == 1
            assert shape_instance is not None
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("文件加载")
    @allure.title("测试加载无形状类的文件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_load_aiotestfile_no_shape(self):
        """测试加载无形状类的文件"""
        # 创建临时测试文件
        test_file = "test_load_file_no_shape.py"
        try:
            with open(test_file, 'w') as f:
                f.write("""
from aiotest.users import User

class TestUser(User):
    weight = 1
    async def run(self):
        pass
""")
            # 测试加载文件（应该失败）
            with pytest.raises(SystemExit):
                load_aiotestfile(test_file)
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("文件加载")
    @allure.title("测试加载多个形状类的文件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_load_aiotestfile_multiple_shapes(self):
        """测试加载多个形状类的文件"""
        # 创建临时测试文件
        test_file = "test_load_file_multiple_shapes.py"
        try:
            with open(test_file, 'w') as f:
                f.write("""
from aiotest.users import User
from aiotest.shape import LoadUserShape

class TestUser(User):
    weight = 1
    async def run(self):
        pass

class TestShape1(LoadUserShape):
    def tick(self):
        pass

class TestShape2(LoadUserShape):
    def tick(self):
        pass
""")
            # 测试加载文件（应该失败）
            with pytest.raises(SystemExit):
                load_aiotestfile(test_file)
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)

    @allure.story("文件加载")
    @allure.title("测试加载失败的文件")
    @allure.severity(allure.severity_level.NORMAL)
    def test_load_aiotestfile_load_error(self):
        """测试加载失败的文件"""
        # 创建临时测试文件，内容会导致加载失败
        test_file = "test_load_file_error.py"
        try:
            with open(test_file, 'w') as f:
                f.write("this is not valid python code")
            # 测试加载文件（应该失败）
            with pytest.raises(SystemExit):
                load_aiotestfile(test_file)
        finally:
            # 清理临时文件
            if os.path.exists(test_file):
                os.remove(test_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
