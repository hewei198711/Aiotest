# encoding: utf-8

from aiotest import AsyncHttpUser, LoadUserShape

# command: aiotest -f stepwise_pressure_shape.py -u 2 -r 2 -t 120
# View test data: http://localhost:8089 

class TestUser(AsyncHttpUser):
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


                   
class TestShape(LoadUserShape):
    stages = [
        {"duration": 600, "user_count": 1000, "rate": 50},
        {"duration": 1200, "user_count": 3000, "rate": 50},
        {"duration": 1800, "user_count": 5000, "rate": 50},
        {"duration": 2400, "user_count": 3000, "rate": 50},
        {"duration": 3600, "user_count": 1000, "rate": 50},
    ]

    def tick(self):
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                tick_data = (stage["user_count"], stage["rate"])
                return tick_data

        return None