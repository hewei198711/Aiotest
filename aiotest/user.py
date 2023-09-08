# encoding: utf-8

import sys
import asyncio
import traceback

from aiohttp.client_exceptions import ClientResponseError
from aiotest import events
from aiotest.client import ClientSession
from aiotest.log import logger


class UserMeta(type):
    """
    Meta class for the main User class. It's used to allow User classes to specify task execution 
    """
    def __new__(mcs, classname, bases, class_dict):
        jobs = []
        for key, value in class_dict.items():
            if key.startswith("test") or key.endswith("test"):
                jobs.append(value)
        class_dict["jobs"] = jobs
        
        return type.__new__(mcs, classname, bases, class_dict)


class User(metaclass=UserMeta):
    host = None
    session = None
    wait_time = 1
    weight = 1
    task = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_start(self):
        """
        Called when a User starts running.
        """
        pass
    
    async def on_stop(self):
        """
        Called when a User stops running (is canceled)
        """
        if not self.session.closed:
            await self.session.close()
        self.session = None
    
    def start_user(self):
        self.task = asyncio.create_task(self.start(), name=type(self).__name__)
        
    async def stop_user(self):
        if not self.task.done():
            self.task.cancel()
        await self.on_stop()
                
    async def start(self):
        """
        Synchronization executes coroutines job from top to bottom
        """
        try:
            try:
                await self.on_start()
                await asyncio.sleep(self.wait_time)
            except:
                await self.on_stop()
                raise                
            while True:
                for job in self.jobs:
                    await job(self)
                    await asyncio.sleep(self.wait_time)
        except asyncio.CancelledError:
            await self.on_stop()
            raise
        except Exception as e:
            await events.user_error.fire(error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())


class AsyncHttpUser(User):
    """
    Represents an AsyncHttp "user" which is to be started and attack the system that is to be load tested.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = ClientSession(base_url=self.host)
