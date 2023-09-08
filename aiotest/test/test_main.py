# encoding: utf-8

import os
import asyncio
import pytest
import allure
import aiohttp
from aiotest.test.log import logger
from aiotest.test.setting import P1, P2, P3
from aiotest.rpc.protocol import Message
from aiotest import User, AsyncHttpUser, LoadUserShape
from aiotest.main import parse_options, find_aiotestfile, load_aiotestfile, is_shape_class, is_user_class


@allure.feature("rpc")
@allure.story("main/parse_options")
class TestArgparse:
    
    @allure.severity(P1)
    @allure.title("parse options")
    async def test_01(self):
        args = await parse_options(args=[
            "-f", "aiotestfile",
            "-u", "100",
            "-r", "10",
        ])
        assert args.host == ""
        assert args.master == False
        assert args.aiotestfile == "aiotestfile"
        assert args.num_users == 100
        assert args.rate == 10
        assert args.loglevel == "INFO"
        assert args.logfile == None
        assert args.show_users_wight == False

        
@allure.feature("main")
@allure.story("main/aiotestfile")
class TestAiotestfile:
    
    mock_user_file_content = """
from aiotest.user import AsyncHttpUser
from aiotest.shape import LoadUserShape


class TestUser(AsyncHttpUser):
    host = "http://127.0.0.1:8080"
    
    async def test_func(self):
        pass

class TestUser02(AsyncHttpUser):
    host = "http://127.0.0.1:8080"
    
    async def test_func(self):
        pass

class UserSubclass03(AsyncHttpUser):
    host = "http://127.0.0.1:8080"
    
    async def func(self):
        pass
        
class UserSubclass():
    host = "http://localhost:8080"

class TestShape(LoadUserShape):
    def tick(self):
        pass
    """
    directory = os.path.dirname(os.path.abspath(__file__))
    filename = "aiotestfile" 

    @classmethod
    def setup_class(cls):
        cls.file_path = os.path.join(cls.directory, "aiotestfile.py")
        with open(cls.file_path, "w") as file:
            file.write(cls.mock_user_file_content)    

    @classmethod
    def teardown_class(cls):
        os.remove(cls.file_path)
            
    @allure.severity(P2)
    @allure.title("find aiotestfile")
    async def test_01(self):
        aiotestfile = find_aiotestfile("aiotest/test/aiotestfile.py")
        assert r"aiotest\test\aiotestfile.py" in aiotestfile

    @allure.severity(P3)
    @allure.title("find aiotestfile not .py")
    async def test_02(self):
        aiotestfile = find_aiotestfile("aiotest/test/aiotestfile")
        assert r"aiotest\test\aiotestfile.py" in aiotestfile

    @allure.severity(P3)
    @allure.title("find aiotestfile not .py")
    async def test_03(self):
        user_classes, shape_class = load_aiotestfile(self.file_path)
        assert len(user_classes) == 2
        logger.debug(user_classes)

    @allure.severity(P3)
    @allure.title("is user class")
    async def test_04(self):
        assert is_user_class(User) is False
        assert is_user_class(AsyncHttpUser) is False
        
        class TestUser01(AsyncHttpUser):
            pass
        
        class User02(AsyncHttpUser):
            pass
        
        assert is_user_class(TestUser01)
        assert is_user_class(User02) is False
        

    @allure.severity(P3)
    @allure.title("is shape class")
    async def test_05(self):
        assert is_shape_class(LoadUserShape) is False
        
        class TestShape(LoadUserShape):
            def tick(self):
                pass

        assert is_shape_class(TestShape)

    @allure.severity(P3)
    @allure.title("load aiotestfile from relative path")
    async def test_06(self):
        user_classes, shape_class = load_aiotestfile(os.path.join("./aiotest/test/", "aiotestfile.py"))
        assert "TestUser" in user_classes
        assert "TestUser02" in user_classes

    @allure.severity(P3)
    @allure.title("load aiotestfile from absolute path")
    async def test_06(self):
        user_classes, shape_class = load_aiotestfile(self.file_path)
        assert "TestUser" in user_classes
        assert "TestUser02" in user_classes

