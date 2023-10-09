## Distributed load test
A single process running Aiotest can simulate a reasonably high throughput. For a simple test plan it should be able to make many thousands of requests per second.

But if you want to run even more load, you'll need to scale out to multiple processes, maybe even multiple machines.

To do this, you start one instance of Aiotest in master mode using the `--master` flag and multiple worker instances using the `--worker` flag. If the workers are not on the same machine as the master you use `--master-host`, `--master-port` to point them to the IP/hostname and port of the machine running the master.

The master instancetells the workers when to start/stop Users.   The workers run your Users and send back statistics to the master.   The master instance doesn't run any Users itself.

Both the master and worker machines must have a copy of the aiotestfile when running Aiotest distributed.

>**Note**
>Because Python cannot fully utilize more than one core per process (see [GIL](https://realpython.com/python-gil/), you should typically run **one worker instance per processor core** on the worker machines in order to utilize all their computing power.
### Example
To start aiotest in master mode:
```console
# linux host:port 192.168.0.10:22 CPU:4
aiotest -f aiotestfile.py --master --expect-workers 8
```
And then on each worker (replace `192.168.0.10` with the IP of the master machine, or leave out the parameter altogether if your workers are on the same machine as the master)
```console
# linux host:port 192.168.0.11:22, CPU:4
aiotest -f aiotestfile.py --worker --master-host "192.168.0.10"
aiotest -f aiotestfile.py --worker --master-host "192.168.0.10"
aiotest -f aiotestfile.py --worker --master-host "192.168.0.10"
aiotest -f aiotestfile.py --worker --master-host "192.168.0.10"

# linux host:port 192.168.0.12:22, CPU:4
aiotest -f aiotestfile.py --worker --master-host "192.168.0.10"
aiotest -f aiotestfile.py --worker --master-host "192.168.0.10"
aiotest -f aiotestfile.py --worker --master-host "192.168.0.10"
aiotest -f aiotestfile.py --worker --master-host "192.168.0.10"
```
### Options
**`--master`**

Sets aiotest in master mode.

**`--worker`**

Sets aiotest in worker mode.

**`--master-host=X.X.X.X`**

Optionally used together with `--worker` to set the hostname/IP of the master node (defaults
to 127.0.0.1)

**`--master-port=5557`**

Optionally used together with `--worker` to set the port number of the master node (defaults to 5557).

**`--master-bind-host=X.X.X.X`**

Optionally used together with `--master`. Determines which network interface the master node
will bind to. Defaults to * (all available interfaces).

**`--master-bind-port=5557`**

Optionally used together with `--master`. Determines what network ports that the master node will
listen to. Defaults to 5557.

**`--expect-workers=X`**

Optionally used together with `--master`. The master node will then wait until X worker
nodes has connected before the test is started.
### Communicating across nodes
In distributed mode, it is recommended to store data in middleware `redis`, and each worker node pulls data from `redis` (for example, pull login account and login password).
```python
from redis import StrictRedis
from aiotest import AsyncHttpUser

db = StrictRedis(
    host="192.168.0.10", 
    port="6379", 
    db=0, 
    decode_responses=True, 
    password="123456"
)
pipe = db.pipeline() 

class TestUserShoppingTrolley(AsyncHttpUser):
    db = db
    async def on_start(self):
        url = "/login"
        username, password = self.db.lpop("userdata")
        data = {"username": username, "password": password}
        async with self.session.post(url=url, data=data) as resp:
            ...
```
### Running distributed with Docker
See [Docker](running-in-docker.md)