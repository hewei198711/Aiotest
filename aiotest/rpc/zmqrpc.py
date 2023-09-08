# encoding: utf-8

import sys
import asyncio
import traceback
from functools import wraps
import zmq
import zmq.asyncio as asynczmq
import zmq.error as zmqerr
import msgpack.exceptions as msgerr
from aiotest.exception import RPCError
from aiotest.rpc.protocol import Message
from aiotest.log import logger


def async_retry(func):
    "Retry 3 times"
    @wraps(func)
    async def wrapper(*args, **kwargs):
        delay = 0
        while delay <= 4:
            try:
                return await func(*args, **kwargs)
            except RPCError:
                delay += 2
                logger.error(f"Exception found on retry {delay/2}: --retry after {delay}")
                await asyncio.sleep(delay)
    return wrapper


class BaseSocket():
    def __init__(self, sock_type):
        context = asynczmq.Context()
        self.socket = context.socket(sock_type)
        self.socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
        self.socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 30)

    @async_retry
    async def send(self, msg):
        try:
            await self.socket.send(msg.serialize(), zmq.NOBLOCK)
        except zmqerr.ZMQError:
            raise RPCError("ZMQ sent failure")

    @async_retry
    async def send_to_worker(self, msg):
        try:
            await self.socket.send_multipart([msg.node_id.encode(), msg.serialize()])
        except zmqerr.ZMQError:
            raise RPCError("ZMQ sent failure")
 
    async def recv(self):
        try:
            data = await self.socket.recv()
            msg = Message.unserialize(data)
        except msgerr.ExtraData:
            raise RPCError("ZMQ interrupted message")
        except zmqerr.ZMQError:
            raise RPCError("ZMQ network broken")
        return msg

    async def recv_from_worker(self):
        try:
            data = await self.socket.recv_multipart()
            addr = data[0].decode()
            msg = Message.unserialize(data[1])
        except (UnicodeDecodeError, msgerr.ExtraData):
            raise RPCError("ZMQ interrupted message")
        except zmqerr.ZMQError:
            raise RPCError("ZMQ interrupted message")
        return addr, msg
    
    def close(self):
        self.socket.close()


class Server(BaseSocket):
    def __init__(self, host, port):
        super().__init__(zmq.ROUTER)
        try:
            self.socket.bind(f"tcp://{host}:{port}")
            self.port = port
        except zmqerr.ZMQError as e:
            raise RPCError(f"Socket bind failure: {e}")


class Client(BaseSocket):
    def __init__(self, host, port, node_id):
        super().__init__(zmq.DEALER)
        self.socket.setsockopt(zmq.IDENTITY, node_id.encode())
        self.socket.connect(f"tcp://{host}:{port}")