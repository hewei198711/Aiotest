# Aiotest


`Aiotest` 是一个开源的 API 性能测试工具，支持 HTTP(S)/HTTP2 等网络协议，基于 `Python Asyncio` 。

## 设计理念

- Asyncio 并发生成user类实例（一个实例模拟一个用户），await串行执行待测 API coroutine（例如各个API互为前置条件的商城下单）
- 可重写user.start()方法，并行执行待测 API coroutine（例如商城首页API互不为前置条件时，可并行）

## 核心特性

- 网络协议：完整支持 HTTP(S)/HTTP2，可扩展支持 WebSocket/TCP/UDP/RPC 等更多协议
- 自动收集用例：通过是否“Test”开头或结尾，自动查找需要执行的User，LoadUserShape类，通过是否“test”开头或“test”结尾，自动查找需要执行的 API coroutine
- 支持多用户类：一个测试文件可以有多个user类（user类不建议内嵌user类），并通过user.weight属性设置不同的执行比例（例如通过购物车提交订单的用户类，直接提交订单的用户类）
- 串行 & 并行执行待测API：默认串行执行 API coroutine，可重写user.start()方法，并行执行代测API（例如商城首页API互不为前置条件时，可并行）
- 数据搜集 & 展示：基于Prometheus收集数据，Grafana展示数据

## 下载安装
```python

pip install aiotest
```

```python
import asyncio
from aiotest import AsyncHttpUser, LoadUserShape
from aiotest import runners

class TestUser(AsyncHttpUser):
    "用户类必须以 Test 开头或结尾，且继承 AsyncHttpUser"
    wait_time = 1 # 每个API request 之间休息时间，默认1秒
    weight = 1 # 用户类权重（可以有多个用户类：方便设置不同用户场景的执行比例）
    host = "https://uat.taobao.com"
    token = None

    async def on_start(self):
        "每个用户类首先，且仅执行一次，用于登录等初始化数据操作"
        url="/login", 
        data={"username": "test01", "password": "123456"}
        # self.session 为 aiohttp.ClientSession() 实例，可重写
        async with self.session.post(url=url, data=data) as resp:
            data = await resp.json()
            self.token = data["token"]

    async def test_search(self):
        "待测试API 必须以 test 开头，或者以 test 结尾"
        url = "/search"
        data = {"keyword": "礼服"}
        async with self.session.post(url=url, json=data) as resp:
            data = await resp.json()
            # 收集请求信息

    async def test_personalInfo(self):
        "待测试API,可通过success，failure 手动设置请求成功/失败"
        url = "/personalInfo"
        async with session.get(url=url) as resp:
            data = await resp.json()
            if data["id"] != "123456":
                resp.failure("id != 123456")

    async def start(self):
        """
        用户类执行测试API的调用程序，默认是从上到下依次阻塞执行所有待测API
        可以重写为异步执行所有代测API(例如商城首页API互不为前置条件时)
        """
        try:
            try:
                await self.on_start()
                await asyncio.sleep(self.wait_time)
            except:
                await self.on_stop()
                raise                
            while True:
                for job in self.jobs:
                    await job(self)
                    await asyncio.sleep(self.wait_time)
        except asyncio.CancelledError:
            await self.on_stop()
            raise
        except Exception as e:
            await events.user_error.fire(runner=runners.global_runner, error=f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())


    class TestShape(LoadUserShape):
        "用户阶梯加载策略类，非必须"
        stages = [
            {"duration": 600, "user_count": 5000, "rate": 500},
            {"duration": 1200, "user_count": 10000, "rate": 500},
            {"duration": 1800, "user_count": 20000, "rate": 500},
            {"duration": 2400, "user_count": 10000, "rate": 500},
            {"duration": 3000, "user_count": 1000, "rate": 500},
        ]

        def tick(self):
            run_time = self.get_run_time()

            for stage in self.stages:
                if run_time < stage["duration"]:
                    tick_data = (stage["user_count"], stage["rate"])
                    return tick_data

            return None

```

## 鸣谢

- Aiotest 为 Locust 的 asyncio 重写版(1.参考Pytest简化待测Class/API收集; 2.抛弃TaskSet类,User类不内嵌User类,仅通过User.weight设置执行比例; 3.抛弃Stats类，通过Prometheus收集数据； 4.抛弃Web类，通过Grafana展示数据)

* Locust: [locust.io](https://locust.io)


