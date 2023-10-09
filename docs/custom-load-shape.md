## Custom load shapes
Sometimes a completely custom shaped load test is required that cannot be achieved by simply setting or changing the user count and spawn rate. For example, you might want to generate a load spike or ramp up and down at custom times. By using a [LoadUserShape](api.md#LoadUserShape) class you have full control over the user count and spawn rate at all times.

Define a class inheriting the LoadUserShape class in your aiotest file. If this type of class is found then it will be automatically used by Aiotest.

In this class you define a `tick()` method that returns a tuple with the desired user count and spawn rate (or `None` to stop the test). Aiotest will call the `tick()` method approximately once per second.

In the class you also have access to the `get_run_time()` method, for checking how long the test has run for.

**Example**
```python
from aiotest import AsyncHttpUser, LoadUserShape, logger

class TestUserShoppingTrolley(AsyncHttpUser):
    """
    Get the shopping cart and submit the order
    """
    weight = 1
    wait_time = 1
    host = "https://taobao.com"
    token = None
    orderid = None

    async def on_start(self):
        url = "/login"
        data = {"username": "admin", "password": "123456"}
        async with self.session.post(url=url, data=data) as resp:
            data = await resp.json()
            self.token = data["token"]

    async def test_get_shopping_trolley(self):
        url = "/GetShoppingTrolley"
        hearders = {"Authorization": self.token}
        async with self.session.get(url=url, hearders=hearders) as resp:
            data = await resp.json()      

    async def order_commit_test(self):
        url = "/orderCommit"
        hearders = {"Authorization": self.token}
        data = {"orderAmount": 100, "coupon": 30}
        async with self.session.post(url=url, json=data, hearders=hearders) as resp:
            data = await resp.json()
            self.orderid = data["order"]["Orderid"]


class TestShape(LoadUserShape):
    stages = [
        {"duration": 180, "user_count": 30, "rate": 30},
        {"duration": 360, "user_count": 60, "rate": 30},
        {"duration": 540, "user_count": 120, "rate": 30},
        {"duration": 720, "user_count": 60, "rate": 30},
        {"duration": 900, "user_count": 30, "rate": 30},
    ]

    def tick(self):
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                tick_data = (stage["user_count"], stage["rate"])
                return tick_data

        return None
```
**Note** The subclass of `LoadUserShape` must startswith or endswith `Test`. aiotestfile contains the `LoadUserShape` subclass, which ignores arguments specified on the command line :`-u`, `-r`, `-t`.