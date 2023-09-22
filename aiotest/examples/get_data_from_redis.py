# encoding: utf-8

import sys
from aiotest import AsyncHttpUser
from redis import StrictRedis

# The data is placed in redis, which is very useful in distributed testing, 
# and can easily ensure the load balance of various working nodes

# command: aiotest -f get_data_from_redis.py -u 2 -r 2 -t 120
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


