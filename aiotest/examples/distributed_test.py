# encoding: utf-8

from redis import StrictRedis
from aiotest import AsyncHttpUser

# command: aiotest -f distributed_test.py --master --expect-workers 4 --master-bind-host "127.0.0.1" --master-bind-port 5557 -u 400 -r 80 -t 3600
# command: aiotest -f distributed_test.py --worker --master-host "127.0.0.1" -master-port 5557
# command: aiotest -f distributed_test.py --worker --master-host "127.0.0.1" -master-port 5557
# command: aiotest -f distributed_test.py --worker --master-host "127.0.0.1" -master-port 5557
# command: aiotest -f distributed_test.py --worker --master-host "127.0.0.1" -master-port 5557

# The data is placed in redis, which is very useful in distributed testing, 
# and can easily ensure the load balance of various working nodes
# View test data: http://localhost:8089 

db = StrictRedis(
    host="127.0.0.1", 
    port=6379, 
    db=0, 
    decode_responses=True, 
    password="123456"
)
db.pipeline()

class TestUser(AsyncHttpUser):
    host = "https://httpbin.org"
    token = None

    async def on_start(self):
        "login and get the token"
        username = self.db.lpop("user")

        url="/login"
        data = {"username": username, "password": 123456}
        async with self.session.post(url=url, data=data) as resp:
            self.token = await resp.json()

    async def test_get(self):
        url = "/get"
        async with self.session.get(url=url) as resp:
            data = await resp.text()
