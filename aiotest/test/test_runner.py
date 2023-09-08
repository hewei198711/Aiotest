# encoding: utf-8

import sys
import traceback
import pytest
import asyncio
import allure
from asyncio import Queue

from aiotest.rpc.zmqrpc import Server, Client
from aiotest.rpc.protocol import Message
from aiotest.user import AsyncHttpUser
from aiotest.stats_exporter import parse_error
from aiotest import events
from aiotest import runners
from aiotest.runners import LocalRunner, MasterRunner, WorkerRunner
from aiotest.shape import LoadUserShape
from aiotest.runners import STATE_INIT, STATE_STARTING, STATE_RUNNING, STATE_MISSING, STATE_STOPPED
from aiotest.test.setting import BASE_URL, P1, P2, P3
from aiotest.test.log import logger

request_dict = {}
error_dict = {}
user_count_dict = {}
test_start = False
test_stop = False


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

async def on_worker_report(worker_id, data):
    global request_dict, user_count_dict
    runner = runners.global_runner
    if worker_id not in runner.workers:
        logger.warning(f"Discarded report from unrecognized worker {worker_id}")
        return
    runner.workers[worker_id].user_count = data["user_count"]
    if data["error"]:  
        data["error"] = parse_error(data["error"])
    request_dict = {
        "request_name": data["request_name"], 
        "request_method": data["request_method"], 
        "response_time": data["response_time"],
        "response_length": data["response_length"],
        "error": data["error"],
    }

    user_count_dict[worker_id] = data["user_count"]

async def on_test_start(runner):
    global test_start
    test_start = True

async def on_test_stop(runner):
    global test_stop
    test_stop = True
    
class mocked_options:
    def __init__(self):
        self.host= BASE_URL
        self.master= False
        self.worker=False
        self.master_host= "localhost"
        self.master_port = 5557
        self.master_bind_host= "*"
        self.master_bind_port= 5557
        self.heartbeat_liveness=3
        self.heartbeat_interval=1
        self.expect_workers= 1
        self.user_count= 2
        self.rate= 1
        self.show_users_wight= False
    
    def reset_stats(self):
        pass

class mocked_rpc:
    def __init__(self, *args, **kwargs):
        self.queue = Queue()
        self.outbox = []
    
    async def mocked_send(self, message):
        "master&worker send"
        await self.queue.put(message.serialize())
    
    async def recv(self):
        "worker recv"
        data = await self.queue.get()
        return Message.unserialize(data)
    
    async def send(self, message):
        "worker send"
        self.outbox.append(message)
    
    async def send_to_worker(self, message):
        "master send"
        self.outbox.append((message.node_id, message))
    
    async def recv_from_worker(self):
        "master recv"
        data = await self.queue.get()
        msg = Message.unserialize(data)
        return msg.node_id, msg


@allure.title("add/remove events.stats_request/user_error/worker_report")
@pytest.fixture(scope="module", autouse=True)
def events_handlers():
    events.stats_request += on_request
    events.user_error += on_error
    events.worker_report += on_worker_report
    events.test_start += on_test_start
    events.test_stop += on_test_stop
    yield
    events.stats_request -= on_request
    events.user_error -= on_error
    events.worker_report -= on_worker_report
    events.test_start -= on_test_start
    events.test_stop -= on_test_stop
 
@allure.title("mock rpc")
@pytest.fixture(scope="function", autouse=True)
def rpc(monkeypatch):
    rpc = mocked_rpc()
    monkeypatch.setattr(Server, "send_to_worker", rpc.send_to_worker)
    monkeypatch.setattr(Server, "recv_from_worker", rpc.recv_from_worker)
    monkeypatch.setattr(Client, "send", rpc.send)
    monkeypatch.setattr(Client, "recv", rpc.recv)
    yield rpc
    monkeypatch.delattr(Server, "send_to_worker", rpc.send_to_worker)
    monkeypatch.delattr(Server, "recv_from_worker", rpc.recv_from_worker)
    monkeypatch.delattr(Client, "send", rpc.send)
    monkeypatch.delattr(Client, "recv", rpc.recv)
  

@allure.title("init request_dict/error_dict/user_count_dict")
@pytest.fixture(scope="function", autouse=True)
async def init_request__error_user_dict(rpc):
    global request_dict, error_dict, user_count_dict, test_start, test_stop
    request_dict = {}
    error_dict = {}
    user_count_dict = {}
    test_start = False
    test_stop = False
    yield
    await runners.global_runner.quit()


@allure.feature("aiotest/runners")
@allure.story("aiotest/runners/LocalRunner")
class TestLocalRunner:
        
    @allure.severity(P2)
    @allure.title("init userclass's host")
    async def test_01(self):
        class MyUser(AsyncHttpUser):
            pass
        
        runner = LocalRunner([MyUser], None, mocked_options())
        runners.global_runner = runner
        runner.weight_users(1)
        assert MyUser.host == runner.options.host

    @allure.severity(P1)
    @allure.title("calculate userclass's weight(equal)")
    async def test_02(self):
        class MyUser(AsyncHttpUser):
            pass

        class MyUser02(AsyncHttpUser):
            pass
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        bucket = runner.weight_users(10)
        assert bucket.count(MyUser) == 5
        assert bucket.count(MyUser02) == 5

    @allure.severity(P2)
    @allure.title("calculate userclass's weight(not equal)")
    async def test_03(self):

        class MyUser(AsyncHttpUser):
            weight = 1

        class MyUser02(AsyncHttpUser):
            weight = 2
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        bucket = runner.weight_users(10)
        assert bucket.count(MyUser) == 3
        assert bucket.count(MyUser02) == 7
 
    @allure.severity(P2)
    @allure.title("calculate userclass's weight(extremum == 1)")
    async def test_04(self):

        class MyUser(AsyncHttpUser):
            weight = 1

        class MyUser02(AsyncHttpUser):
            weight = 2
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        bucket = runner.weight_users(1)
        assert len(bucket) == 1
        assert bucket.count(MyUser02) == 1
 
    @allure.severity(P1)
    @allure.title("start user_count==4, then start user_count==2(userclasses)")
    async def test_05(self):

        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        class MyUser02(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        await runner.start(user_count=4, rate=4)
        await asyncio.sleep(1.5)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 4
        await runner.start(user_count=2, rate=2)
        await asyncio.sleep(1.5)
        assert runner.user_count == 2
        
    @allure.severity(P2)
    @allure.title("start user_count==2, then start user_count==4(userclasses)")
    async def test_06(self):

        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        class MyUser02(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        await runner.start(user_count=2, rate=2)
        await asyncio.sleep(1.3)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 2
        await runner.start(user_count=4, rate=4)
        await asyncio.sleep(1.3)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 4
        
    @allure.severity(P1)
    @allure.title("start_users user_count==2, then start_users user_count==4(userclasses)")
    async def test_07(self):

        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        class MyUser02(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        await runner.start_users(user_count=2, rate=2)
        await asyncio.sleep(1.2)
        assert runner.state == STATE_STARTING
        assert runner.user_count == 2
        await runner.start_users(user_count=2, rate=2)
        await asyncio.sleep(1.2)
        assert runner.state == STATE_STARTING
        assert runner.user_count == 4
        
    @allure.severity(P1)
    @allure.title("stop all user tasks")
    async def test_08(self):

        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        class MyUser02(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        await runner.start(user_count=4, rate=4)
        await asyncio.sleep(1.5)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 4
        await runner.stop()
        await asyncio.sleep(0.5)
        assert runner.state == STATE_STOPPED
        assert runner.user_count == 0
        
    @allure.severity(P1)
    @allure.title("stop_user portion user task")
    async def test_09(self):

        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        class MyUser02(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        await runner.start(user_count=4, rate=4)
        await asyncio.sleep(1.5)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 4
        await runner.stop_users(user_count=2, rate=2)
        await asyncio.sleep(1)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 2
        
    @allure.severity(P2)
    @allure.title("stop_user portion user task(rate < user_count)")
    async def test_10(self):

        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        class MyUser02(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        await runner.start(user_count=4, rate=4)
        await asyncio.sleep(1.5)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 4
        await runner.stop_users(user_count=2, rate=1)
        await asyncio.sleep(1)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 2
        
    @allure.severity(P1)
    @allure.title("quit")
    async def test_11(self):

        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        class MyUser02(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass
                
        runner = LocalRunner([MyUser, MyUser02], None, mocked_options())
        runners.global_runner = runner
        await runner.start(user_count=4, rate=4)
        await asyncio.sleep(1.5)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 4
        await runner.quit()
        await asyncio.sleep(1)
        assert runner.state == STATE_STOPPED
        assert runner.user_count == 0
        for task in runner.tasks:
            assert task.done() is True
        
    @allure.severity(P1)
    @allure.title("load user shape")
    async def test_12(self):

        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        class TestShape(LoadUserShape):
            def tick(self):
                run_time = self.get_run_time()
                if run_time < 2:
                    return (2, 2)
                elif run_time < 4:
                    return (4, 4)
                elif run_time < 6:
                    return (2, 2)
                else:
                    return None
                
        runner = LocalRunner([MyUser], TestShape(), mocked_options())
        runners.global_runner = runner
        runner.start_shape()
        await asyncio.sleep(1.3)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 2
        await asyncio.sleep(1.7)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 4
        await asyncio.sleep(2.3)
        assert runner.state == STATE_RUNNING
        assert runner.user_count == 2

    @allure.severity(P1)
    @allure.title("events.test_start and events.test_stop")
    async def test_13(self):

        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass
                
        runner = LocalRunner([MyUser], None, mocked_options())
        runners.global_runner = runner
        await runner.start(user_count=2, rate=2)
        await asyncio.sleep(1.3)
        assert test_start is True
        assert test_stop is False
        await runner.stop()
        await asyncio.sleep(1.3)
        assert test_start is True
        assert test_stop is True

            
@allure.feature("aiotest/runners")
@allure.story("aiotest/runners/MasterRunner")
class TestMasterRunner:
        
    @allure.severity(P2)
    @allure.title("worker send 'ready' to master")
    async def test_01(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        await rpc.mocked_send(Message("ready", None, "worker01"))
        master = MasterRunner([MyUser], None, mocked_options())
        runners.global_runner = master
        await asyncio.sleep(0.1)
        assert master.worker_count == 1
        assert "worker01" in master.workers
        
        await rpc.mocked_send(Message("ready", None, "worker02"))
        await rpc.mocked_send(Message("ready", None, "worker03"))
        await rpc.mocked_send(Message("ready", None, "worker04"))
        await asyncio.sleep(0.1)
        assert master.worker_count == 4
        
        await rpc.mocked_send(Message("quitted", None, "worker01"))
        await asyncio.sleep(0.1)
        assert master.worker_count == 3

    @allure.severity(P2)
    @allure.title("worker send 'starting' to master")
    async def test_02(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        await rpc.mocked_send(Message("ready", None, "worker01"))
        master = MasterRunner([MyUser], None, mocked_options())
        runners.global_runner = master
        await asyncio.sleep(0.1)
        assert master.worker_count == 1
        assert "worker01" in master.workers
        
        await rpc.mocked_send(Message("starting", None, "worker01"))
        await asyncio.sleep(0.1)
        assert master.workers["worker01"].state == STATE_STARTING

    @allure.severity(P2)
    @allure.title("worker send 'start_complete' to master")
    async def test_03(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        await rpc.mocked_send(Message("ready", None, "worker01"))
        await rpc.mocked_send(Message("ready", None, "worker02"))
        master = MasterRunner([MyUser], None, mocked_options())
        runners.global_runner = master
        await rpc.mocked_send(Message("start_complete", {"user_count": 2}, "worker01"))
        await asyncio.sleep(0.1)
        assert master.worker_count == 2
        assert master.user_count == 2
        assert master.workers["worker01"].user_count == 2
        
        await rpc.mocked_send(Message("start_complete", {"user_count": 2}, "worker02"))
        await asyncio.sleep(0.1)
        assert master.worker_count == 2
        assert master.user_count == 4
        assert master.workers["worker01"].user_count == 2
        assert master.workers["worker02"].user_count == 2

    @allure.severity(P2)
    @allure.title("worker send 'stats' to master(not error)")
    async def test_04(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        stats = {
            "request_name": "/get", 
            "request_method": "GET", 
            "response_time": 230,
            "response_length": 60,
            "error": None,
            "user_count": 2
        }
        await rpc.mocked_send(Message("ready", None, "worker01"))
        master = MasterRunner([MyUser], None, mocked_options())
        runners.global_runner = master
        await rpc.mocked_send(Message("starting", None, "worker01"))
        await asyncio.sleep(0)
        await rpc.mocked_send(Message("start_complete", {"user_count": 2}, "worker01"))
        await asyncio.sleep(0.01)
        await rpc.mocked_send(Message("stats", stats, "worker01"))
        await asyncio.sleep(0.01)
        assert master.worker_count == 1
        assert master.user_count == 2
        assert master.workers["worker01"].user_count == 2
        user_count = stats.pop("user_count")
        assert request_dict == stats
        assert user_count_dict["worker01"] == user_count
        
    @allure.severity(P2)
    @allure.title("worker send 'stopped' to master")
    async def test_05(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        await rpc.mocked_send(Message("ready", None, "worker01"))
        master = MasterRunner([MyUser], None, mocked_options())
        runners.global_runner = master
        await rpc.mocked_send(Message("starting", None, "worker01"))
        await asyncio.sleep(0)
        await rpc.mocked_send(Message("start_complete", {"user_count": 2}, "worker01"))
        await asyncio.sleep(0.01)
        await rpc.mocked_send(Message("stopped", None, "worker01"))
        await asyncio.sleep(0.01)
        assert master.worker_count == 0
        assert master.user_count == 0
        await rpc.mocked_send(Message("ready", None, "worker01"))
        await asyncio.sleep(0.01)
        assert master.worker_count == 1
        assert master.user_count == 0
        
    @allure.severity(P3)
    @allure.title("worker send 'quit' to master")
    async def test_06(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        await rpc.mocked_send(Message("ready", None, "worker01"))
        master = MasterRunner([MyUser], None, mocked_options())
        runners.global_runner = master
        await rpc.mocked_send(Message("starting", None, "worker01"))
        await asyncio.sleep(0)
        await rpc.mocked_send(Message("start_complete", {"user_count": 2}, "worker01"))
        await asyncio.sleep(0.01)
        await rpc.mocked_send(Message("stopped", None, "worker01"))
        await asyncio.sleep(0.01)
        assert master.worker_count == 0
        assert master.user_count == 0
        await rpc.mocked_send(Message("ready", None, "worker01"))
        await asyncio.sleep(0.01)
        assert master.worker_count == 1
        assert master.user_count == 0
        await rpc.mocked_send(Message("quitted", None, "worker01"))
        await asyncio.sleep(0.1)
        assert master.worker_count == 0
        assert master.user_count == 0        

    @allure.severity(P3)
    @allure.title("worker send 'error' to master")
    async def test_07(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        await rpc.mocked_send(Message("ready", None, "worker01"))
        master = MasterRunner([MyUser], None, mocked_options())
        runners.global_runner = master
        await rpc.mocked_send(Message("starting", None, "worker01"))
        await asyncio.sleep(0)
        await rpc.mocked_send(Message("start_complete", {"user_count": 2}, "worker01"))
        await asyncio.sleep(0.01)
        await rpc.mocked_send(Message("error", {"error": "this is error"}, "worker01"))
        await asyncio.sleep(0.01)
        assert "this is error" in error_dict["error"]
     
    @allure.severity(P2)
    @allure.title("worker user count")
    async def test_08(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        stats = {
            "request_name": "/get", 
            "request_method": "GET", 
            "response_time": 230,
            "response_length": 60,
            "error": None,
            "user_count": 2
        }
        await rpc.mocked_send(Message("ready", None, "worker01"))
        master = MasterRunner([MyUser], None, mocked_options())
        runners.global_runner = master
        await rpc.mocked_send(Message("starting", None, "worker01"))
        await asyncio.sleep(0)
        await rpc.mocked_send(Message("stats", stats, "worker01"))
        await asyncio.sleep(0.01)
        assert master.user_count == 2
     
    @allure.severity(P3)
    @allure.title("worker missing")
    async def test_09(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        await rpc.mocked_send(Message("ready", None, "worker01"))
        master = MasterRunner([MyUser], None, mocked_options())
        runners.global_runner = master
        await rpc.mocked_send(Message("starting", None, "worker01"))
        await asyncio.sleep(0)
        await rpc.mocked_send(Message("start_complete", {"user_count": 2}, "worker01"))
        await asyncio.sleep(6)   
        assert master.user_count == 0
        assert master.worker_count == 0
        assert master.workers["worker01"].state == STATE_MISSING
     

@allure.feature("aiotest/runners")
@allure.story("aiotest/runners/WorkerRunner")
class TestWorkerRunner:
        
    @allure.severity(P2)
    @allure.title("worker send 'ready' to master")
    async def test_01(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        worker = WorkerRunner([MyUser], None, mocked_options())
        runners.global_runner = worker
        await asyncio.sleep(0.1)
        assert "ready" in [msg.type for msg in rpc.outbox]

    @allure.severity(P1)
    @allure.title("worker recv 'start'")
    async def test_02(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        worker = WorkerRunner([MyUser], None, mocked_options())
        runners.global_runner = worker
        await asyncio.sleep(0.1)
        # master send
        await rpc.mocked_send(
            Message(
                "start", 
                {
                    "user_count": 2,
                    "rate": 2,
                    "host": BASE_URL,
                },
                rpc.outbox[0].node_id
            )
        )
        await asyncio.sleep(1)
        assert "starting" in [msg.type for msg in rpc.outbox]
        assert worker.user_count == 2
        await asyncio.sleep(0.1)
        assert worker.worker_state == STATE_RUNNING
        assert "start_complete" in [msg.type for msg in rpc.outbox]

    @allure.severity(P2)
    @allure.title("worker recv 'stop'")
    async def test_03(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        worker = WorkerRunner([MyUser], None, mocked_options())
        runners.global_runner = worker
        await asyncio.sleep(0.1)
        # master send
        await rpc.mocked_send(
            Message(
                "start", 
                {
                    "user_count": 2,
                    "rate": 2,
                    "host": BASE_URL,
                },
                rpc.outbox[0].node_id
            )
        )
        await asyncio.sleep(1)
        assert worker.user_count == 2
        # master send
        await rpc.mocked_send(Message("stop", None, rpc.outbox[0].node_id))
        await asyncio.sleep(1)
        assert "stopped" in [msg.type for msg in rpc.outbox]
        assert worker.user_count == 0
        assert worker.worker_state == STATE_INIT

    @allure.severity(P2)
    @allure.title("worker recv 'quit'")
    async def test_04(self, rpc):
        class MyUser(AsyncHttpUser):
            wait_time = 0
            async def test(self):
                pass

        worker = WorkerRunner([MyUser], None, mocked_options())
        runners.global_runner = worker
        await asyncio.sleep(0.1)
        # master send
        await rpc.mocked_send(
            Message(
                "start", 
                {
                    "user_count": 2,
                    "rate": 2,
                    "host": BASE_URL,
                },
                rpc.outbox[0].node_id
            )
        )
        await asyncio.sleep(1)
        assert worker.user_count == 2
        # master send
        await rpc.mocked_send(Message("stop", None, rpc.outbox[0].node_id))
        await asyncio.sleep(1)
        assert "stopped" in [msg.type for msg in rpc.outbox]
        assert worker.user_count == 0
        assert worker.worker_state == STATE_INIT
        # master send
        await rpc.mocked_send(Message("quit", None, rpc.outbox[0].node_id))
        await asyncio.sleep(4)
        assert len(worker.tasks) == 1
        assert worker.tasks[0].get_name() == "worker_run"
