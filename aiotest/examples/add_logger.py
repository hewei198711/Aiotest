# encoding: utf-8

from aiotest import AsyncHttpUser, logger

# command: aiotest -f add_logger.py -u 2 -r 2 -t 120 -L DEBUG --logfile log.log
# View test data: http://localhost:8089 

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
            logger.debug(self.token)

    async def test_get(self):
        url = "/get"
        async with self.session.get(url=url) as resp:
            data = await resp.text()
            logger.debug(data)

    async def test_post(self):
        url = "/status/200"
        async with self.session.post(url=url) as resp:
            data = await resp.text()
            logger.debug(data)

