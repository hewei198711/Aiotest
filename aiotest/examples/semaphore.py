# encoding: utf-8

from asyncio.locks import Semaphore
from aiotest import AsyncHttpUser, events

# Second kill activity, all users have logged in, complete the collection, and then synchronize to perform subsequent tests.
# command: aiotest -f semaphore.py -u 20 -r 2 -t 1200
# View test data: http://localhost:8089 


all_user_start_complete = Semaphore()
all_user_start_complete.acquire()


async def on_start_complete(user_count):
    all_user_start_complete.release()

          
events.start_complete += on_start_complete 
          
    
class TestUser(AsyncHttpUser):
    wait_time = 1
    weight = 1
    host = "https://httpbin.org"
    token = None

    async def on_start(self):
        "login and get the token"
        url="/post"
        async with self.session.post(url=url) as resp:
            self.token = await resp.json()

    async def test_get(self):
        url = "/get"
        async with self.session.get(url=url) as resp:
            data = await resp.text()

    async def test_post(self):
        url = "/status/200"
        async with self.session.post(url=url) as resp:
            data = await resp.text()

