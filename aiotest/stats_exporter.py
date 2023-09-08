# encoding: utf-8

import re
import psutil
import asyncio
import hashlib
from prometheus_client import Histogram, Gauge, Counter, start_http_server
from aiotest import events
from aiotest.rpc.protocol import Message
from aiotest.log import logger

CPU_MONITOR_INTERVAL = 5 # CPU 监控时间间隔
USER_MONITOR_INTERVAL = 5 # USER_COUNT 监控时间间隔
STATSERROR = {} # 保存error

BUCKETS = (300, 1000, 8000, float('inf'))
LABELS = ["name", "method", "code"]

aiotest_response_times = Histogram(name='aiotest_response_times', documentation='aiotest response times', labelnames=LABELS, buckets=BUCKETS)
aiotest_response_content_length = Gauge(name='aiotest_response_content_length', documentation='aiotest response content length', labelnames=LABELS)
aiotest_response_failure = Counter(name='aiotest_response_failure', documentation='aiotest response failure', labelnames=["name","method", "error"])
aiotest_user_error = Counter(name='aiotest_user_error', documentation='aiotest user error', labelnames=["error"])
aiotest_workers_user_count = Gauge(name='aiotest_workers_user_count', documentation='aiotest workers user count', labelnames=["node"])
aiotest_workers_cpu_usage = Gauge(name='aiotest_workers_cpu_usage', documentation='aiotest workers cpu usage', labelnames=["node"])

code_regexp = re.compile(r"^\{\"code\":(\d{3})")


def parse_error(error):
    string_error = repr(error)
    if string_error.find("当前登录已失效，请重新登录") > 0:
        string_error = re.sub(r", \'time\': \'20\S+\'", "",string_error)
        if string_error.find("time") > 0:
            string_error = re.sub(r',\"time\":\"20\S+\"', "",string_error)
        return string_error

    target = "object at 0x"
    target_index = string_error.find(target)
    if target_index < 0:
        return string_error
    start = target_index + len(target) - 2
    end = string_error.find(">", start)
    if end < 0:
        return string_error
    hex_address = string_error[start:end]
    return string_error.replace(hex_address, "0x....")


async def on_request(runner, request_name, request_method, response_time, response_length, error):
    if not error:
        if type(runner).__name__ == "WorkerRunner":
            try:
                await runner.worker.send(
                    Message(
                        "stats", 
                        {
                            "request_name": request_name, 
                            "request_method": request_method, 
                            "response_time": response_time,
                            "response_length": response_length,
                            "error": error,
                            "user_count": runner.user_count
                        }, 
                        runner.worker_id
                    )
                )
            except:
                logger.error("Connection lost to master server. Aborting...")
        else:
            aiotest_response_times.labels(request_name, request_method, 200).observe(response_time)
            aiotest_response_content_length.labels(request_name, request_method, 200).set(response_length)  
    else:
        error = parse_error(error) 
        if type(runner).__name__ == "WorkerRunner":
            try:
                await runner.worker.send(
                    Message(
                        "stats", 
                        {
                            "request_name": request_name, 
                            "request_method": request_method, 
                            "response_time": response_time,
                            "response_length": response_length,
                            "error": error,
                            "user_count": runner.user_count
                        }, 
                        runner.worker_id
                    )
                )
            except:
                logger.error("Connection lost to master server. Aborting...")
        else:
            aiotest_response_times.labels(request_name, request_method, 400).observe(response_time)
            aiotest_response_content_length.labels(request_name, request_method, 400).set(response_length)
            aiotest_response_failure.labels(request_name, request_method, error).inc()
            key = create_key(error, request_name, request_method)
            if not STATSERROR.get(key):
                STATSERROR[key] = 1
                logger.error(f"{request_name}: {error}")
            else:
                STATSERROR[key] += 1

      
async def on_error(runner, error):
    error = parse_error(error)
    if type(runner).__name__ == "WorkerRunner":
        try:
            await runner.worker.send(Message("error", {"error": error}, runner.worker_id))
        except:
            logger.error("Connection lost to master server. Aborting...")
    else:
        aiotest_user_error.labels(error).inc()
        key = create_key(error)
        if not STATSERROR.get(key):
            STATSERROR[key] = 1
            logger.error(error)
        else:
            STATSERROR[key] += 1
        

async def on_worker_report(runner, worker_id, data):
    if worker_id not in runner.workers:
        logger.warning(f"Discarded report from unrecognized worker {worker_id}")
        return
    runner.workers[worker_id].user_count = data["user_count"]
    if not data["error"]:  
        aiotest_response_times.labels(data["request_name"], data["request_method"], 200).observe(data["response_time"])
        aiotest_response_content_length.labels(data["request_name"], data["request_method"], 200).set(data["response_length"])
    else:
        aiotest_response_times.labels(data["request_name"], data["request_method"], 400).observe(data["response_time"])
        aiotest_response_content_length.labels(data["request_name"], data["request_method"], 400).set(data["response_length"])
        aiotest_response_failure.labels(data["request_name"], data["request_method"], data["error"]).inc()
        key = create_key(data["error"], data["request_name"], data["request_method"])
        if not STATSERROR.get(key):
            STATSERROR[key] = 1
            logger.error(f'{data["request_name"]}: {data["error"]}')
        else:
            STATSERROR[key] += 1

    aiotest_workers_user_count.labels(worker_id).set(data["user_count"])         


async def exporter_cpu_usage(runner):
    process = psutil.Process()
    while True:
        cpu_usage = process.cpu_percent() # 当前进程CPU利用率的百分比
        if type(runner).__name__ == "MasterRunner":
            aiotest_workers_cpu_usage.labels("Master").set(cpu_usage)
            for id, worker in runner.workers.items():
                aiotest_workers_cpu_usage.labels(id).set(worker.cpu_usage)
            if cpu_usage >= 90:
                logger.warning(f"Master CPU usage {cpu_usage}!")
        elif type(runner).__name__ == "LocalRunner":
            aiotest_workers_cpu_usage.labels("Local").set(cpu_usage)  
            if cpu_usage >= 90:
                logger.warning(f"Local CPU usage {cpu_usage}!")
        else:
            runner.cpu_usage = cpu_usage
        await asyncio.sleep(CPU_MONITOR_INTERVAL)


async def exporter_user_count(runner):
    while True:
        aiotest_workers_user_count.labels("local").set(runner.user_count)
        await asyncio.sleep(USER_MONITOR_INTERVAL)

       
async def prometheus_server():
    start_http_server(8089)


events.stats_request += on_request
events.user_error += on_error
events.worker_report += on_worker_report


def create_key(error, name=None, method=None):
    key = f"{method}.{name}.{error}"
    return hashlib.md5(key.encode('utf-8')).hexdigest()   

