# encoding: utf-8

import json
import pytest
import asyncio
import allure
from timeit import default_timer
from aiotest.client import ClientSession
from aiotest.stats_exporter import parse_error
from aiotest import events
from aiotest.test.setting import BASE_URL, P1, P2, P3
from aiotest.test.log import logger


request_dict = {}


async def on_request(runner, request_name, request_method, response_time, response_length, error):
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


@allure.title("add/remove events.stats_request")
@pytest.fixture(scope="module", autouse=True)
def events_handlers():
    events.stats_request += on_request
    yield
    events.stats_request -= on_request

@allure.title("init request_dict/error_dict")
@pytest.fixture(scope="function", autouse=True)
def init_request_and_error_dict():
    global request_dict
    request_dict = {}


@allure.feature("aiotest/client")
@allure.story("aiotest/client/ClientSession")
class TestClientSession:
        
    @classmethod
    @allure.title("start ClientSession")
    def setup_class(cls):
        cls.session = ClientSession(BASE_URL)

    @classmethod
    @allure.title("close ClientSession")
    def terdown_class(cls):
        cls.session.close()
                
    @allure.severity(P1)
    @allure.title("get method")
    async def test_01(self):
        start_time = default_timer()
        async with self.session.get("/", timeout=8) as resp: 
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
            assert text == "asyncio sleep"
        assert request_dict["request_name"] == "/"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len("asyncio sleep")  
        assert request_dict["error"] == None  
    
    @allure.severity(P1)
    @allure.title("streaming")
    async def test_02(self): 
        start_time = default_timer()
        async with self.session.get("/streaming/30") as resp:
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/streaming/30"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)  
        assert request_dict["error"] == None   

    @allure.severity(P1)
    @allure.title("redirect")
    async def test_03(self):
        
        url = "/redirect?url=/redirect?delay=0.2"
        start_time = default_timer()
        async with self.session.get(url) as resp:
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/fast"
        assert request_dict["request_method"] == "GET"
        assert 205 < abs(request_dict["response_time"] - times) > 200
        assert request_dict["response_length"] == len(text)  
        assert request_dict["error"] == None   
                        
    @allure.severity(P2)
    @allure.title("redirect and name")
    async def test_04(self):
        start_time = default_timer()        
        async with self.session.post("/redirect", name="/redirect") as resp:
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/redirect"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 10
        assert request_dict["response_length"] == len(text)  
        assert request_dict["error"] == None  
            
    @allure.severity(P1)
    @allure.title("cookie")
    async def test_05(self):
        start_time = default_timer()   
        async with self.session.post("/set_cookie?name=testcookie&value=1337") as resp:
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/set_cookie"
        assert request_dict["request_method"] == "POST"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)  
        assert request_dict["error"] == None
        
        start_time = default_timer()   
        async with self.session.get("/get_cookie?name=testcookie") as resp:
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/get_cookie"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)
        assert request_dict["error"] == None
    
    @allure.severity(P2)
    @allure.title("head method")
    async def test_06(self):
        start_time = default_timer()   
        async with self.session.head("/request_method") as resp:
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/request_method"
        assert request_dict["request_method"] == "HEAD"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == 4 
        assert request_dict["error"] == None
        
    @allure.severity(P2)
    @allure.title("delete method")
    async def test_07(self):
        start_time = default_timer()   
        async with self.session.delete("/request_method") as resp:
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/request_method"
        assert request_dict["request_method"] == "DELETE"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)  
        assert request_dict["error"] == None

    @allure.severity(P2)
    @allure.title("all method")
    async def test_08(self):
        start_time = default_timer()   
        async with self.session.options("/request_method") as resp:
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/request_method"
        assert request_dict["request_method"] == "OPTIONS"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)
        assert request_dict["error"] == None
        assert set(["OPTIONS", "DELETE", "PUT", "GET", "POST", "HEAD", "PATCH"]) == set(resp.headers["allow"].split(", "))
            
    @allure.severity(P1)
    @allure.title("ClientResponseError")
    async def test_09(self):
        start_time = default_timer()   
        async with self.session.get('/wrong_url/01') as resp:
            assert resp.status == 404
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/wrong_url/01"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)
        assert request_dict["error"].find("ClientResponseError") >= 0

    @allure.severity(P1)
    @allure.title("TimeoutError")
    async def test_10(self):
        with pytest.raises(TimeoutError):
            async with self.session.get("/consistent", timeout=0.1) as resp:
                text = await resp.text()
                 
    @allure.severity(P2)
    @allure.title("ClientResponseError")
    async def test_11(self):
        start_time = default_timer()   
        async with self.session.get('/wrong_url/01') as resp:
            assert resp.status == 404
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/wrong_url/01"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)
        assert request_dict["error"].find("ClientResponseError") >= 0

    @allure.severity(P2)
    @allure.title("500")
    async def test_11(self):
        start_time = default_timer()   
        async with self.session.get('/fail') as resp:
            assert resp.status == 500
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
        assert request_dict["request_name"] == "/fail"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)
        assert request_dict["error"].find("ClientResponseError") >= 0

    @allure.severity(P2)
    @allure.title("TypeError")
    async def test_12(self):
        start_time = default_timer()   
        async with self.session.get('/') as resp:
            assert resp.status == 200
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
            text["id"]
        assert request_dict["request_name"] == "/"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)
        assert request_dict["error"].find("TypeError") >= 0

    @allure.severity(P2)
    @allure.title("KeyError")
    async def test_13(self):
        start_time = default_timer()   
        async with self.session.get('/key') as resp:
            assert resp.status == 200
            data = await resp.json()
            times = int((default_timer() - start_time) * 1000)
            data["key03"]
        assert request_dict["request_name"] == "/key"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["error"].find("KeyError") >= 0

    @allure.severity(P2)
    @allure.title("AssertionError")
    async def test_14(self):
        start_time = default_timer()   
        async with self.session.get('/key') as resp:
            assert resp.status == 200
            data = await resp.json()
            times = int((default_timer() - start_time) * 1000)
            assert data["key01"] == 3
        assert request_dict["request_name"] == "/key"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["error"].find("AssertionError") >= 0

    @allure.severity(P2)
    @allure.title("success")
    async def test_15(self):
        start_time = default_timer()   
        async with self.session.get('/fast') as resp:
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
            if resp.status == 200:
                resp.success()
        assert request_dict["request_name"] == "/fast"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)
        assert request_dict["error"] is None

    @allure.severity(P2)
    @allure.title("failure")
    async def test_16(self):
        start_time = default_timer()   
        async with self.session.get('/fast') as resp:
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
            if resp.status == 200:
                resp.failure("my is a failure")
        assert request_dict["request_name"] == "/fast"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)
        assert request_dict["error"].find("CatchResponseError('my is a failure')") >= 0

    @allure.severity(P2)
    @allure.title("success error")
    async def test_17(self):
        start_time = default_timer()   
        async with self.session.get('/fail') as resp:
            text = await resp.text()
            times = int((default_timer() - start_time) * 1000)
            resp.success()
        assert request_dict["request_name"] == "/fail"
        assert request_dict["request_method"] == "GET"
        assert abs(request_dict["response_time"] - times) < 5
        assert request_dict["response_length"] == len(text)
        assert request_dict["error"] is None


