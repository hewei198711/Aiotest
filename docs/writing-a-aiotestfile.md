## Writing a aiotestfile
Now, lets look at a more complete/realistic example of what your tests might look like:
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
    
    async def test_pay(self):
        url = "/Pay"
        hearders = {"Authorization": self.token}
        data = {"id": self.orderid}
        async with self.session.post(url=url, json=data, headers=self.headers, name="My Pay") as resp:    
            data = await resp.json()


class UserOrderCommitTest(AsyncHttpUser):
    """
    Direct order submission
    """
    weight = 4
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

    async def order_commit_test(self):
        url = "/orderCommit"
        hearders = {"Authorization": self.token}
        data = {"orderAmount": 100, "coupon": 30}
        async with self.session.post(url=url, json=data, hearders=hearders) as resp:
            data = await resp.json()
            self.orderid = data["order"]["Orderid"]
    
    async def test_pay(self):
        url = "/Pay"
        hearders = {"Authorization": self.token}
        data = {"id": self.orderid} 
        async with self.session.post(url=url, json=data, headers=self.headers, name="My Pay") as resp:    
            data = await resp.json()
```
**Let’s break it down**
```python
from aiotest import AsyncHttpUser, LoadUserShape, logger
```

A aiotest file is just a normal Python module, it can import code from other files or packages.

### **User**
```python
class TestUserShoppingTrolley(AsyncHttpUser):
    ...

class UserOrderCommitTest(AsyncHttpUser):
    ...
```
Here we define a class for the users that we will be simulating(The class must startswith or endswith `Test`, otherwise aiotest will ignore the class). It inherits from [AsyncHttpUser](api.md#AsyncHttpUser) which gives each user a `session` attribute, which is an instance of [ClientSession](api.md#ClientSession), that can be used to make HTTP requests to the target system that we want to load test. When a test starts, aiotest will create an instance of this class for every user that it simulates, and each of these users will start running within their own [asyncio.Task](https://docs.python.org/zh-cn/3/library/asyncio-task.html).

For a file to be a valid aiotestfile it must contain at least one class inheriting from [User](api.md#User)
#### **wait_time**
```python
wait_time = 1
```
Our class defines a `wait_time` that will make the simulated users wait 1 seconds after each api coroutine.
#### **host**
```python
host = "https://taobao.com"
```
The host attribute is a URL prefix to the host that is to be loaded.
Usually, this is specified on the command line, using the`--host` option, when aiotest is started.

If the command line specifies the `--host` attribute, it replaces the `host` attribute set in the user class
#### **weight**
```python
class TestUserShoppingTrolley(AsyncHttpUser):
    weight=1
    ...
class UserOrderCommitTest(AsyncHttpUser):
    weight=4
    ...
```
We use the weight attribute to set different weights for the user class and flexibly set different load test scenarios. eg:The number of instances of the `UserOrderCommitTest` class would be four times that of the `TestUserShoppingTrolley` class. If we were to simulate 100 customers, So the `UserOrderCommitTest` class will instantiate 80 and the `TestUserShoppingTrolley` class will instantiate 20
#### **session**
```python
async with self.session.post(url=url, json=data, hearders=hearders) as resp:
    ...
```
The property `self.session` is an instance of the [ClientSession](api.md#ClientSession) class that makes it possible to make HTTP requests that will be logged by aiotest.[see more](https://docs.aiohttp.org/en/stable/client_quickstart.html)
#### **on_start() and on_stop()**
```python
async def on_start(self):
    url = "/login"
    data = {"username": "admin", "password": "123456"}
    async with self.session.post(url=url, data=data) as resp:
        data = await resp.json()
        self.token = data["token"]

async def on_stop(self):
    super().on_stop()

```
When the `user` starts the operation, the [on_start](api.md#ClientSession) method will be called first, and the [on_stop](api.md#ClientSession) method will be called only once at the end. The `on_start` method is basically used for `login` and obtaining the `token`
### **Job**
```python
async def test_get_shopping_trolley(self):
    ...

async def order_commit_test(self):
    ...
```
Methods must startswith or endswith `test` ,otherwise aiotest will ignore the methods. For every running user,
Aiotest creates a `asyncio.Task`, that will call those methods.
#### **name**
```python
async def test_pay(self):
    ... 
    async with self.session.post(url=url, name="My Pay") as resp:    
        ...
```
When aiotest collects the status of each request (response_time, response_size, code), the request is named by `url` by default, and you can rename it by setting the parameter `name` in the request
#### **success() failure(exc)**
```python
async def order_commit_test(self):
    "The use of assert is recommended"
    async with self.session.post(url=url) as resp:
        data = await resp.json()
        assert data["order"]["Orderid"].startswith("2023")

async def test_pay(self):
    "It is not recommended to display calls to the success,failure methods"
    async with self.session.post(url=url) as resp:
        if resp.status < 400:
            resp.success()
        else:
            resp.failure(exc="An Error Occurred")
```
Use the `success` method to mark the request as a success, even if the response code is incorrect, and the `failure` method to mark the request as a failure, even if the response code is correct.

When async with context exits, aiotest will automatically call the `Event.stats_request` and record the request information (request_name, request_method, response_time, response_length, error). It is not recommended to call the `success` and `failure` methods, it is recommended to use `assert` to raise an exception (see [pytest](https://www.osgeo.cn/pytest/getting-started.html#assert-that-a-certain-exception-is-raised))

