# encoding: utf-8

import pytest
import allure
from aiotest.test.setting import P1, P2, P3
from aiotest.rpc.protocol import Message
from aiotest.rpc import zmqrpc
from aiotest.test.log import logger

@allure.feature("rpc")
@allure.story("rpc/msgpack")
class TestMsgpack:
    
    @allure.severity(P1)
    @allure.title("message serialize/unserialize")
    async def test_01(self):
        
        msg = Message(
            "stats", 
            {"name": "/getname", "method": "GET", "response_time": 960, "response_length": 56, "user_count": 1000}, 
            "127.0.0.1_asdfzxcvfd"
        )
        
        packb = msg.serialize()
        rebuilt = Message.unserialize(packb)

        assert msg.type == rebuilt.type
        assert msg.data == rebuilt.data
        assert msg.node_id == rebuilt.node_id
                        

@allure.feature("rpc")
@allure.story("rpc/zmq")
class TestZmq:
    
    @classmethod
    @allure.title("Start ZMQ")
    def setup_class(cls):
        cls.server = zmqrpc.Server("127.0.0.1", 5557)
        cls.client = zmqrpc.Client("127.0.0.1", 5557, "worker_01")
    
    @classmethod
    @allure.title("Close ZMQ")    
    def teardown_class(cls):
        cls.server.socket.close()
        cls.client.socket.close()
    
    @allure.severity(P1)
    @allure.title("client send / server revc")
    async def test_01(self):
        await self.client.send(
            Message(
            "stats", 
            {"name": "/getname", "method": "GET", "response_time": 960, "response_length": 56, "user_count": 1000}, 
            "worker_01"
            )
        )
        addr, msg = await self.server.recv_from_worker()
        assert addr == "worker_01"
        assert msg.type == "stats" and msg.node_id == "worker_01"
        assert msg.data == {"name": "/getname", "method": "GET", "response_time": 960, "response_length": 56, "user_count": 1000}

    @allure.severity(P1)
    @allure.title("server send / client revc")
    async def test_02(self):
        await self.server.send_to_worker(
            Message(
            "test", 
            "message", 
            "worker_01"
        ))
        msg = await self.client.recv()
        assert msg.type == "test"
        assert msg.data == "message"
        assert msg.node_id == "worker_01"
                