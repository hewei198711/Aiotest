# encoding: utf-8

import sys
import socket
import asyncio
from uuid import uuid4
from aiotest.log import logger
from aiotest import events
from aiotest.rpc.protocol import Message
from aiotest.rpc.zmqrpc import Server, Client
from aiotest.exception import RPCError
from aiotest.stats_exporter import exporter_cpu_usage, exporter_user_count, prometheus_server

global_runner = None

HEARTBEAT_INTERVAL = 1 # worker 心跳监控时间间隔
HEARTBEAT_LIVENESS = 3 # 心跳
FALLBACK_INTERVAL = 5 # worker信息接收失败后，重新获取信息间隔
STATE_INIT, STATE_STARTING, STATE_RUNNING, STATE_STOPPED, STATE_MISSING = [
    "ready",
    "starting",
    "running", 
    "stopped", 
    "missing"
]

    
class Runner:
    def __init__(self, user_classes, shape_class, options):
        self.user_classes = user_classes
        self.shape_class = shape_class
        self.options = options
        self.cpu_usage = 0
        self.state = STATE_INIT
        self.user_instances = []
        self.tasks = []
        self.is_quit = False
        
    def __del__(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
               
    @property
    def user_count(self):
        "Returns the number of running user tasks, a user equals a task"
        return len([instances for instances in self.user_instances if not instances.task.done()])
    
    def update_state(self, new_state):
        logger.debug(f"Updating state to {new_state}, old state was {self.state}")   
        self.state = new_state
                       
    def weight_users(self, amount):
        """
        Distributes the amount of users for each User-class according to it's weight returns a list "bucket" with the weighted users
        """
        weight_sum = 0
        for user in self.user_classes:
            if self.options.host:
                user.host = self.options.host
            try:
                if isinstance(user.weight, int) and user.weight >= 1:
                    weight_sum += user.weight
                else:
                    raise ValueError("weigth value must be an int type and >= 1")
            except KeyError:
                raise KeyError("Userclass must have weight attribute")
            
        residuals = {}
        bucket = []
        for user in self.user_classes:
            # create users depending on weight
            percent = user.weight / weight_sum
            num_users = round(amount * percent)
            residuals[user] = amount * percent - num_users
            
            bucket.extend([user for i in range(num_users)])
            
        if len(bucket) < amount:
            for user in [l for l, r in sorted(residuals.items(), key=lambda x: x[1], reverse=True)][:amount-len(bucket)]:
                bucket.append(user)
        elif len(bucket) > amount:
            for user in [l for l, r in sorted(residuals.items(), key=lambda x: x[1])][:len(bucket)-amount]:
                bucket.remove(user)
        # [<class 'User01'>, <class 'User02'>,...]    
        return bucket
    
    async def start(self, user_count, rate):
        "Create user tasks for a load test master entry"
        if not isinstance(user_count, int) or user_count <= 0:
            logger.warning(f"{user_count} mast be int type and >= 1")
            sys.exit(1)
        if rate <= 0 or rate > user_count:
            logger.warning(f"{rate} mast > 0 and < user_count {user_count}") 
            sys.exit(1) 
        if rate % 1 != 0:
            logger.warning(f"{rate} rate fractional part is't 0") 
        
        # Dynamically changing the user count
        if self.state in [STATE_STARTING, STATE_RUNNING]:
            logger.debug(f"Updating running test with {user_count} users, {rate:.2f} rate.")
            self.update_state(STATE_STARTING)
            if self.user_count > user_count:
                # stop some users
                stop_count = self.user_count - user_count
                await self.stop_users(stop_count, rate)
                self.update_state(STATE_RUNNING)
            elif self.user_count < user_count:
                # start some users
                start_count = user_count - self.user_count
                await self.start_users(start_count, rate)
                self.update_state(STATE_RUNNING)
            else:
                self.update_state(STATE_RUNNING)
        elif self.state == STATE_INIT:
            await self.start_users(user_count, rate)
            self.update_state(STATE_RUNNING)
            await events.start_complete.fire(user_count=self.user_count)
        else:
            logger.error(f"runner state is {self.state}")
            sys.exit(1)
    
    async def start_users(self, user_count, rate):  
        "Create a specified number of user tasks, a user equals a task"         
        bucket = self.weight_users(user_count) # [<class 'User01'>, <class 'User02'>,...]  
        if self.state == STATE_INIT:
            self.update_state(STATE_STARTING)
            
        existing_count = self.user_count
        logger.info(f"starting {len(bucket)} users at the rate {rate} users/s, ({existing_count} users already running)...")
        start_count = dict((u.__name__, 0) for u in self.user_classes) # {'User01': 0, 'User02': 0...}
        
        sleep_time = 1 / rate
        for i in range(len(bucket)):
            user_class = bucket.pop()
            start_count[user_class.__name__] += 1
            
            new_user = user_class()
            new_user.start_user()
            self.user_instances.append(new_user)
            
            await asyncio.sleep(sleep_time) 
            if self.user_count % 10 == 0:
                logger.debug(f"{self.user_count} users started")
            
        if not bucket:
            logger.info(f"All users started: {', '.join([f'{name}:{count}' for name, count in start_count.items()])}")
        else:
            logger.error(f"{bucket}  have user_class don't started")
            sys.exit(1)
        
    async def stop_users(self, user_count, rate):  
        "Cancels a specified number of user tasks"
        bucket = self.weight_users(user_count) # [<class 'User01'>, <class 'User02'>,...]  
        user_count = len(bucket)
        stop_users = []
        for instances in self.user_instances:
            if not instances.task.done():
                for user_class in bucket:
                    if isinstance(instances, user_class):
                        stop_users.append(instances)
                        bucket.remove(user_class)
                        break
                    
        if rate >= user_count:
            sleep_time = 0
            logger.info(f"Stopping {user_count} users immediately")
        else:
            sleep_time = 1 / rate
            logger.info(f"Stoping {user_count} users at rate of {rate} users/s")

        for instances in stop_users:
            await instances.stop_user()
            await asyncio.sleep(sleep_time)

        self.user_instances = [instances for instances in self.user_instances if not instances.task.done()]
        stop_users = [instances for instances in stop_users if not instances.task.done()]
        if stop_users:
            logger.warning(f"There are still user tasks uncancelled: {len(stop_users)}")
        
    async def stop(self):
        "Cancel all user tasks"
        logger.debug("Stopping all users")
        await self.stop_users(self.user_count, self.user_count)
        await asyncio.sleep(0.5)
        logger.debug(f"all user task is done: {all([instances.task.done() for instances in self.user_instances])}")
        for task in self.tasks:
            if task.get_name() == "users_tasks" and not task.done():
                task.cancel()
                self.tasks.remove(task)
                break
        self.update_state(STATE_STOPPED)

    async def quit(self):
        "Exit the load test and cancel all runner tasks"
        if not self.is_quit:
            self.is_quit = True
            await self.stop()
            await asyncio.sleep(0.5)
            await events.quitting.fire()
            for task in self.tasks:
                if not task.done() and task != asyncio.current_task():
                    task.cancel()
            await asyncio.sleep(0.1)
            self.tasks = [task for task in self.tasks if not task.done()]
            logger.debug(f"runner's tasks is done: {len(self.tasks) == 1}")
      
    def start_shape(self):
        "Create a load test policy task"
        shape_task = asyncio.create_task(self.shape_run(), name="shape_task")
        self.tasks.append(shape_task)
    
    async def shape_run(self):
        "Execute the specified load test policy"
        logger.info("Shape starting")
        shape_last = None
        while True:
            shape_new = self.shape_class.tick()
            if shape_new is None:
                logger.info("Shape test stopping")
                await self.quit()
                return
            elif shape_last == shape_new:
                await asyncio.sleep(1)
            else:
                logger.debug(shape_new)
                user_count, rate = shape_new
                logger.info(f"Shape test updating to {user_count} users at {rate} rate")
                await self.start(user_count=user_count, rate=rate)
                shape_last = shape_new
 

class LocalRunner(Runner):
    def __init__(self, user_classes, shape_class, options):
        super().__init__(user_classes, shape_class, options)
        user_count_task = asyncio.create_task(exporter_user_count(), name="user_count_task")
        prometheus_task = asyncio.create_task(prometheus_server(), name="prometheus")
        monitor_cpu_task = asyncio.create_task(exporter_cpu_usage("Local"), name="monitor_cpu")
        
        self.tasks.append(user_count_task)
        self.tasks.append(prometheus_task)
        self.tasks.append(monitor_cpu_task)
    
    async def start(self, user_count, rate):
        if rate > 100:
            logger.warning("Your selected rate is very high (>100), and this is known to sometimes cause issues. Do you really need to ramp up that fast?")
        if self.state == STATE_INIT:
            await events.test_start.fire(runner=self)
        for task in asyncio.all_tasks():
            if task.get_name() == "users_tasks" and not task.done():
                # cancel existing task(name='users_tasks') before we start a new one
                task.cancel()
                break
        users_tasks = asyncio.create_task(super().start(user_count, rate), name="users_tasks")
        self.tasks.append(users_tasks)
    
    async def stop(self):
        # if self.state == STATE_STOPPED:
        #     return
        await super().stop()
        await events.test_stop.fire(runner=self)


class DistributedRunner(Runner):
    def __init__(self, user_classes, shape_class, options):
        super().__init__(user_classes, shape_class, options)        
        self.master_host = options.master_host
        self.master_port = options.master_port
        self.master_bind_host = options.master_bind_host
        self.master_bind_port = options.master_bind_port
        self.heartbeat_liveness = HEARTBEAT_LIVENESS
        self.heartbeat_interval = HEARTBEAT_INTERVAL
        self.connection_broken = False # 连接断了
  
  
class WorkerNode:
    def __init__(self, id, state=STATE_INIT, heartbeat_liveness=HEARTBEAT_LIVENESS):
        self.id = id
        self.state = state
        self.user_count = 0
        self.heartbeat = heartbeat_liveness
        self.cpu_usage = 0


class MasterRunner(DistributedRunner):
    """
    Runner used to run distributed load tests across multiple processes and/or machines.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class WorkerNodesDict(dict):
            def get_by_state(self, state):
                return [c for c in self.values() if c.state == state]
            
            @property
            def all(self):
                return self.values()
            
            @property
            def ready(self):
                return self.get_by_state(STATE_INIT)
            @property
            def starting(self):
                return self.get_by_state(STATE_STARTING)
            
            @property
            def running(self):
                return self.get_by_state(STATE_RUNNING)
            
            @property
            def missing(self):
                return self.get_by_state(STATE_MISSING)
        
        self.workers = WorkerNodesDict()
        self.server = Server(self.master_bind_host, self.master_bind_port)
        
        worekr_heartbeat_task = asyncio.create_task(self.worker_heartbeat(), name="worekr_heartbeat")
        worekr_listener_task = asyncio.create_task(self.worekr_listener(), name="worekr_listener")
        prometheus_task = asyncio.create_task(prometheus_server(), name="prometheus")
        monitor_cpu_task = asyncio.create_task(exporter_cpu_usage("Master"), name="monitor_cpu")
        
        self.tasks.append(worekr_heartbeat_task)
        self.tasks.append(worekr_listener_task)
        self.tasks.append(prometheus_task)
        self.tasks.append(monitor_cpu_task)
            
    @property
    def user_count(self):
        return sum([c.user_count for c in self.workers.values()])

    @property
    def worker_count(self):
        return len(self.workers.ready) + len(self.workers.starting) + len(self.workers.running)
   
    async def start(self, user_count, rate):
        num_workers = self.worker_count
        if not num_workers:
            logger.warning("You are running in distributed mode but have no worker servers connected. Please connect workers prior to swarming.")
            return
        
        worker_host = self.options.host
        worker_user_count = user_count // (num_workers or 1) # 每个worker分配user_count
        worker_rate = rate / (num_workers or 1) # 每个worker生成user速率
        remainig = user_count % num_workers # 剩下的user_count
        
        logger.info(f"Sending jobs of {worker_user_count} users and {worker_rate:.2f} rate to {num_workers} ready workers")
        if worker_rate > 100:
            logger.warning("Your selected rate is very high (>100/worker), and this is known to sometimes cause issues. Do you really need to ramp up that fast?")
        if self.state == STATE_INIT:
            await events.test_start.fire(runner=self)
            self.update_state(STATE_STARTING)
        for worker in (self.workers.ready +self.workers.starting +self.workers.running):
            data = {
                "user_count": worker_user_count,
                "rate": worker_rate,
                "host": worker_host
            }
            if remainig > 0:
                data["user_count"] += 1
                remainig -= 1
                
            logger.debug(f"Sending start users message to worker {worker.id}")
            await self.server.send_to_worker(Message("start", data, worker.id))

    async def stop(self):
        logger.debug("Stopping...")  
        # 避免直到tick（）发出另一个变化信号时才停止
        if self.shape_class:
            self.tactics_current = None
        for worker in self.workers.all:
            logger.debug(f"Sending stop message to worker {worker.id}")
            await self.server.send_to_worker(Message("stop", None, worker.id))

        await events.test_stop.fire(runner=self)
        self.update_state(STATE_STOPPED)

    async def quit(self):
        logger.debug("Quitting...")
        if not self.is_quit:
            self.is_quit = True
            await self.stop()
            await asyncio.sleep(0.5)
                
            for worker in self.workers.all:
                logger.debug(f"Sending quit message to worker {worker.id}")
                await self.server.send_to_worker(Message("quit", None, worker.id))
            
            await asyncio.sleep(0.5) # wait for final stats report from all workers
            await events.quitting.fire()
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            self.server.close()
    
    async def worker_heartbeat(self):
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if self.connection_broken:
                await self.reset_connection()
                continue
            for worker in self.workers.all:
                if worker.heartbeat < 0 and worker.state != STATE_MISSING:
                    logger.warning(f"Worker {worker.id} failed to send heartbeat, setting state to missing.")
                    worker.state = STATE_MISSING
                    worker.user_count = 0
                    if self.worker_count - len(self.workers.missing) <= 0:
                        logger.warning("The last worker went missing, stopping test.")
                        await self.stop()
                else:
                    worker.heartbeat -= 1
                    
    async def reset_connection(self):
        logger.info("Reset connection to worker")
        try:
            self.server.close()
            self.server = Server(self.master_bind_host, self.master_bind_port)
        except RPCError as e:
            logger.error(f"Temporary failure when resetting connection: {e}, will retry later.")

    async def worekr_listener(self): 
        while True:
            try:
                worker_id, msg = await self.server.recv_from_worker()
                msg.node_id = worker_id            
            except RPCError as e:
                logger.error(f"RPCError found when receiving from worker: {e}")
                self.connection_broken = True
                await asyncio.sleep(FALLBACK_INTERVAL)
                continue
            self.connection_broken = False
            if msg.type == "heartbeat":
                if worker_id in self.workers:
                    c = self.workers[worker_id]
                    c.heartbeat = HEARTBEAT_LIVENESS
                    c.state = msg.data["state"]
                    c.cpu_usage = msg.data["cpu_usage"]
                    if c.cpu_usage >= 90:
                        logger.warning(f"Worker {worker_id} exceeded CPU threshold")
            elif msg.type == "stats":
                if worker_id not in self.workers:
                    logger.warning(f"Discarded report from unrecognized worker {worker_id}")
                else:
                    self.workers[worker_id].user_count = msg.data["user_count"]
                await events.worker_report.fire(worker_id=worker_id, data=msg.data)
            elif msg.type == "error":
                await events.user_error.fire(error=msg.data["error"])   
            elif msg.type == "ready":
                self.workers[worker_id] = WorkerNode(id=worker_id)
                logger.info(f"Worker {worker_id} reported as ready. Currently {self.worker_count} workers ready to swarm.")
                if self.state in [STATE_STARTING, STATE_RUNNING]:
                    # balance the load distribution when new worker joins
                    self.start(self.options.user_count, self.options.rate)
            elif msg.type == "starting":
                self.workers[worker_id].state = STATE_STARTING
            elif msg.type == "start_complete":
                self.workers[worker_id].state = STATE_RUNNING
                self.workers[worker_id].user_count = msg.data["user_count"]
                if len(self.workers.running) == len(self.workers.all):
                    self.update_state(STATE_RUNNING)
                    await events.start_complete.fire(user_count = self.user_count)
            elif msg.type == "stopped":
                if worker_id in self.workers:
                    del self.workers[worker_id]
                    logger.info(f"Removing {worker_id} worker from running workers")
            elif msg.type == "quitted":
                if worker_id in self.workers:
                    del self.workers[worker_id]
                    logger.info(f"Worker {worker_id} quitted. Currently {self.worker_count} workers connected.")


class WorkerRunner(DistributedRunner):
    "Runner used to run distributed load tests across multiple processes and/or machines."
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.worker_state = STATE_INIT
        # 主机ip地址 + 随机码
        self.worker_id = socket.gethostbyname(socket.gethostname()) + "_" + uuid4().hex
        self.worker = Client(self.master_host, self.master_port, self.worker_id)
        
        heartbeat_task = asyncio.create_task(self.heartbeat(), name="heartbeat")
        worker_run_task = asyncio.create_task(self.worker_run(), name="worker_run")
        monitor_cpu_task = asyncio.create_task(exporter_cpu_usage("Worker"), name="monitor_cpu")
        
        self.tasks.append(heartbeat_task)
        self.tasks.append(worker_run_task)
        self.tasks.append(monitor_cpu_task)
        
        events.start_complete += self.on_start_complete
        events.quitting += self.on_quitting
 
    async def on_start_complete(self, user_count):
        await self.worker.send(Message("start_complete", {"user_count":user_count}, self.worker_id))
        self.worker_state = STATE_RUNNING

    async def on_quitting(self):
        await self.worker.send(Message("quitted", None, self.worker_id)) 
    
    async def heartbeat(self):
        while True:
            try:
                await self.worker.send(
                    Message(
                        "heartbeat",
                        {"state": self.worker_state, "cpu_usage": self.cpu_usage},
                        self.worker_id
                    )
                )
            except RPCError as e:
                logger.error(f"RPCError found when sending heartbeat: {e}")
                self.reset_connection()
            finally:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
    
    async def reset_connection(self):
        logger.info("Reset connection to master")
        try:
            self.worker.close()
            self.worker = Client(self.master_host, self.master_port, self.worker_id)
        except RPCError as e:
            logger.error(f"Temporary failure when resetting connection: {e}, will retry later.")
        
    async def worker_run(self):
        await self.worker.send(Message("ready", None, self.worker_id))
        while True:
            try:
                msg = await self.worker.recv()             
            except RPCError as e:
                logger.error(f"RPCError found when receiving from master: {e}")
                continue
            if msg.type == "start":
                self.worker_state = STATE_STARTING
                await self.worker.send(Message("starting", None, self.worker_id))
                job = msg.data
                self.options.host = job["host"]
                for task in asyncio.all_tasks():
                    if task.get_name() == "users_tasks" and not task.done():
                        # cancel existing task(name='start_user') before we start a new one
                        task.cancel()
                        break
                users_tasks = asyncio.create_task(self.start(job["user_count"], job["rate"]), name="users_tasks")
                self.tasks.append(users_tasks)
            elif msg.type == "stop":
                await self.stop()
                await self.worker.send(Message("stopped", None, self.worker_id))
                self.worker_state = STATE_STOPPED
                await self.worker.send(Message("ready", None, self.worker_id))
                self.worker_state = STATE_INIT
            elif msg.type == "quit":
                logger.info("Got quit message from master, shutting down...")
                await self.quit()
            
    async def quit(self):
        "Exit the load test and cancel all runner tasks"
        await super().quit()
        if self.worker:
            self.worker.close()
