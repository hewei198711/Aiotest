# encoding: utf-8

from aiotest import AsyncHttpUser

# command: aiotest -f name_property.py -u 2 -r 2 -t 120
# View test data: http://localhost:8089 

class TestUser(AsyncHttpUser):
    wait_time = 1
    weight = 1
    host = "https://httpbin.org"
    token = None

    async def on_start(self):
        "login and get the token"
        url="/post"
        async with self.session.post(url=url, name="custom_name_one") as resp:
            self.token = await resp.json()

    async def test_get(self):
        url = "/get"
        async with self.session.get(url=url, name="custom_name_two") as resp:
            data = await resp.text()

    async def test_post(self):
        url = "/status/200"
        async with self.session.post(url=url, name="custom_name_three") as resp:
            data = await resp.text()

