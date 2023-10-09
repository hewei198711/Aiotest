## Seckill semaphore wait
In the mall test, there is a seckill scenario, customers have logged in, entered the activity page, and made all the preparations for placing orders, when it is allowed to place orders, all customers place orders at the same time.

We need to have customers log in, wait for everyone to log in, and then place orders at the same time.

```python
from aiotest import AsyncHttpUser, LoadUserShape, logger, events
from redis import StrictRedis
from asyncio.locks import Semaphore

db = StrictRedis(
    host="192.168.0.10", 
    port="6379", 
    db=0, 
    decode_responses=True, 
    password="123456"
)
pipe = db.pipeline()

all_user_start_complete = Semaphore()
all_user_start_complete.acquire()

async def on_init():
    db.set("seckill", 1, ex=3600)


async def on_start_complete(user_count, runner):
    if type(runner).__name__ != "WorkerRunner":
        db.set("seckill", 0, ex=3600)
        all_user_start_complete.release()
        return
    while True:
        if db.get("seckil") == 0:
            all_user_start_complete.release()
            return
        await asyncio.sleep(1)

events.init += on_init
events.start_complete += on_start_complete 


class TestUser(AsyncHttpUser):
    host = "https://uat.taobao.com"
    token = None

    async def on_start(self):
        url = "/login"
        data = {"username": "admin", "password": "123456"}
        async with self.session.post(url=url, data=data) as resp:
            data = await resp.json()
            self.token = data["token"]
        # Block, wait for all customers to log in
        all_user_start_complete.wait()

    async def test_search(self):
        url = "/search"
        hearders = {"Authorization": self.token}
        data = {"keyword": "F22"}
        async with self.session.post(url=url, hearders=hearders, json=data) as resp:
            data = await resp.json()      

    async def test_personal_info(self):
        url = "/personalInfo"
        async with self.session.get(url=url, hearders=hearders) as resp:
            data = await resp.json()

```