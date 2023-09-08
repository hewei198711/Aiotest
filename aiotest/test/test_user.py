# encoding: utf-8

import sys
import traceback
import pytest
import asyncio
import allure
from aiotest.user import AsyncHttpUser
from aiotest.stats_exporter import parse_error
from aiotest import events
from aiotest.test.setting import BASE_URL, P1, P2, P3


request_dict = {}
error_dict = {}


async def on_request(request_name, request_method, response_time, response_length, error):
    global request_dict
    request_dict = {}
    if error:
        error = parse_error(error)
    request_dict = {
        "request_name": request_name, 
        "request_method": request_method, 
        "response_time": response_time,
        "response_length": response_length,
        "error": error,
    }


async def on_error(error):
    global error_dict
    error_dict = {}
    if error:
        error = parse_error(error)
    error_dict = {
        "error": error,
    }


@allure.title("add/remove events.stats_request/user_error")
@pytest.fixture(scope="module", autouse=True)
def events_handlers():
    events.stats_request += on_request
    events.user_error += on_error
    yield
    events.stats_request -= on_request
    events.user_error -= on_error

@allure.title("init request_dict/error_dict")
@pytest.fixture(scope="function", autouse=True)
def init_request_and_error_dict():
    global request_dict, error_dict
    request_dict = {}
    error_dict = {}



@allure.feature("aiotest/user")
@allure.story("aiotest/user/AsyncHttpUser")
class TestAsyncHttpUser:
        
    @allure.severity(P1)
    @allure.title("user jobs")
    async def test_01(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def test_get(self):
                pass
            async def get_test(self):
                pass
            async def get(self):
                pass
        u =MyUser()
        assert u.jobs == [MyUser.test_get, MyUser.get_test]
        u.on_stop()

    @allure.severity(P2)
    @allure.title("on_start add job")
    async def test_02(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def on_start(self):
                self.jobs = [MyUser.get01]
            async def get01(self):
                async with self.session.get("/") as resp: 
                    text = await resp.text()
            async def get02(self):
                pass
            async def get03(self):
                pass
            async def start(self):
                try:
                    await self.on_start()
                    await asyncio.sleep(self.wait_time)
                    for job in self.jobs:
                        await job(self)
                        await asyncio.sleep(self.wait_time)
                except asyncio.CancelledError:
                    await self.on_stop()
                    raise
                except Exception as e:
                    await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

        u =MyUser()
        await u.start()
        assert u.jobs == [MyUser.get01]
        assert request_dict["request_name"] == "/"
        assert request_dict["request_method"] == "GET"
        assert 150 > request_dict["response_time"] > 80
        assert request_dict["response_length"] == len("asyncio sleep")  
        assert request_dict["error"] == None
        assert error_dict.get("error", None) is None
                
    @allure.severity(P1)
    @allure.title("user start jobs")
    async def test_03(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def test_get(self):
                async with self.session.get("/") as resp: 
                    text = await resp.text()
            async def start(self):
                try:
                    await self.on_start()
                    await asyncio.sleep(self.wait_time)
                    for job in self.jobs:
                        await job(self)
                        await asyncio.sleep(self.wait_time)
                except asyncio.CancelledError:
                    await self.on_stop()
                    raise
                except Exception as e:
                    await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

        u =MyUser()
        await u.start()
        assert request_dict["request_name"] == "/"
        assert request_dict["request_method"] == "GET"
        assert 120 > request_dict["response_time"] > 80
        assert request_dict["response_length"] == len("asyncio sleep")  
        assert request_dict["error"] == None
        assert error_dict.get("error", None) is None

    @allure.severity(P2)
    @allure.title("user on_start raise error")
    async def test_04(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def on_start(self):
                async with self.session.get("/") as resp: 
                    text = await resp.text()
                    raise KeyError
            async def start(self):
                try:
                    await self.on_start()
                    await asyncio.sleep(self.wait_time)
                    for job in self.jobs:
                        await job(self)
                        await asyncio.sleep(self.wait_time)
                except asyncio.CancelledError:
                    await self.on_stop()
                    raise
                except Exception as e:
                    await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

        u =MyUser()
        await u.start()
        assert request_dict["request_name"] == "/"
        assert request_dict["request_method"] == "GET"
        assert 130 > request_dict["response_time"] > 80
        assert request_dict["response_length"] == len("asyncio sleep")  
        assert request_dict["error"].find("KeyError") >= 0
        assert error_dict.get("error", None) is None

    @allure.severity(P1)
    @allure.title("user.job raise error")
    async def test_05(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def test_get(self):
                async with self.session.get("/") as resp: 
                    text = await resp.text()
                    raise KeyError
            async def start(self):
                try:
                    await self.on_start()
                    await asyncio.sleep(self.wait_time)
                    for job in self.jobs:
                        await job(self)
                        await asyncio.sleep(self.wait_time)
                except asyncio.CancelledError:
                    await self.on_stop()
                    raise
                except Exception as e:
                    await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

        u =MyUser()
        await u.start()
        assert request_dict["request_name"] == "/"
        assert request_dict["request_method"] == "GET"
        assert 120 > request_dict["response_time"] > 80
        assert request_dict["response_length"] == len("asyncio sleep")  
        assert request_dict["error"].find("KeyError") >= 0
        assert error_dict.get("error", None) is None

    @allure.severity(P2)
    @allure.title("user.job raise NameError error")
    async def test_06(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def test_get(self):
                async with self.session.get("/fast") as resp:
                    text = await resp.text() 
                    raise NameError
            async def start(self):
                try:
                    await self.on_start()
                    await asyncio.sleep(self.wait_time)
                    for job in self.jobs:
                        await job(self)
                        await asyncio.sleep(self.wait_time)
                except asyncio.CancelledError:
                    await self.on_stop()
                    raise
                except Exception as e:
                    await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

        u =MyUser()
        await u.start()
        assert request_dict == {}
        assert error_dict.get("error", None).find("NameError") >= 0
        u.on_stop()

    @allure.severity(P2)
    @allure.title("user.job raise KeyError error")
    async def test_07(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def test_get(self):
                async with self.session.get("/") as resp:
                    text = await resp.text() 
                    raise KeyError
            async def start(self):
                try:
                    await self.on_start()
                    await asyncio.sleep(self.wait_time)
                    for job in self.jobs:
                        await job(self)
                        await asyncio.sleep(self.wait_time)
                except asyncio.CancelledError:
                    await self.on_stop()
                    raise
                except Exception as e:
                    await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

        u =MyUser()
        await u.start()
        assert request_dict["request_name"] == "/"
        assert request_dict["request_method"] == "GET"
        assert 130 > request_dict["response_time"] > 80
        assert request_dict["response_length"] == len("asyncio sleep")  
        assert request_dict["error"].find("KeyError") >= 0
        assert error_dict.get("error", None) is None

    @allure.severity(P2)
    @allure.title("user.job raise CancelledError error")
    async def test_08(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def test_get(self):
                async with self.session.get("/") as resp:
                    text = await resp.text() 
                    raise asyncio.CancelledError
            async def start(self):
                try:
                    await self.on_start()
                    await asyncio.sleep(self.wait_time)
                    for job in self.jobs:
                        await job(self)
                        await asyncio.sleep(self.wait_time)
                except asyncio.CancelledError:
                    await self.on_stop()
                    raise
                except Exception as e:
                    await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

        u =MyUser()
        with pytest.raises(asyncio.exceptions.CancelledError):
            await u.start()
        assert request_dict == {}
        assert error_dict.get("error", None) is None

    @allure.severity(P2)
    @allure.title("user.job success() and raise KeyError error")
    async def test_09(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def test_get(self):
                async with self.session.get("/") as resp:
                    text = await resp.text() 
                    resp.success()
                    raise KeyError
            async def start(self):
                try:
                    await self.on_start()
                    await asyncio.sleep(self.wait_time)
                    for job in self.jobs:
                        await job(self)
                        await asyncio.sleep(self.wait_time)
                except asyncio.CancelledError:
                    await self.on_stop()
                    raise
                except Exception as e:
                    await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

        u =MyUser()
        await u.start()
        assert request_dict["request_name"] == "/"
        assert request_dict["request_method"] == "GET"
        assert 120 > request_dict["response_time"] > 80
        assert request_dict["response_length"] == len("asyncio sleep")  
        assert request_dict["error"] is None
        assert error_dict.get("error", None).find("KeyError") >= 0
        u.on_stop()

    @allure.severity(P2)
    @allure.title("user.job failure() and raise KeyError error")
    async def test_10(self):
        class MyUser(AsyncHttpUser):
            host = BASE_URL
            wait_time = 0
            async def test_get(self):
                async with self.session.get("/") as resp:
                    text = await resp.text() 
                    resp.failure("my failuer")
                    raise KeyError
            async def start(self):
                try:
                    await self.on_start()
                    await asyncio.sleep(self.wait_time)
                    for job in self.jobs:
                        await job(self)
                        await asyncio.sleep(self.wait_time)
                except asyncio.CancelledError:
                    await self.on_stop()
                    raise
                except Exception as e:
                    await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

        u =MyUser()
        await u.start()
        assert request_dict["request_name"] == "/"
        assert request_dict["request_method"] == "GET"
        assert 120 > request_dict["response_time"] > 80
        assert request_dict["response_length"] == len("asyncio sleep")  
        assert request_dict["error"].find("my failuer") >= 0
        assert error_dict.get("error", None).find("KeyError") >= 0
        u.on_stop()











