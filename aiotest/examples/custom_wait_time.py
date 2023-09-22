# encoding: utf-8

from aiotest import AsyncHttpUser

# command: aiotest -f custom_wait_time.py -u 2 -r 2 -t 120
# View test data: http://localhost:8089 

class TestUser(AsyncHttpUser):
    # The default wait is 1 second
    wait_time = 0 # not wait
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


