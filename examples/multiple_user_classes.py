# encoding: utf-8

from aiotest import AsyncHttpUser

# The execution weight of TestUser01 : TestUser02 is 2:1
# command: aiotest -f multiple_user_classes.py -u 2 -r 2 -t 120
# View test data: http://localhost:8089 

class TestUser01(AsyncHttpUser):
    # The default weight is 1 
    weight = 2
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


class TestUser02(AsyncHttpUser):
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