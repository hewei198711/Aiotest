# encoding: utf-8

from aiotest import AsyncHttpUser, events

"""
events:
    init_command_line_parser
    init
    test_start
    start_complete
    stats_request
    user_error
    worker_report
    test_stop
    quitting

command: aiotest -f add_events.py -u 2 -r 2 -t 120
View test data: http://localhost:8089
"""

async def on_init_command_line_parser(parser):
    parser.add_argument(
        '--my-order',
        type=str,
        default='',
        help="It is my order"
    )

async def on_init():
    print(f"init...")

async def on_test_start(runner):
    print("test start...")

async def on_start_complete(user_count, runner):
    print(f"Number of simulated users: {user_count}")

async def on_stats_request(runner, request_name, request_method, response_time, response_length, error):
    stats = {
        "request_name": request_name, 
        "request_method": request_method, 
        "response_time": response_time,
        "response_length": response_length,
        "error": error,
        "user_count": runner.user_count,
    }
    print(stats)

async def on_user_error(runner, error):
    print(error)

async def on_worker_report(runner, worker_id, data):
    print(f"{worker_id}: {data}")

async def on_test_stop(runner):
    print("test stop...")

async def on_quitting():
    print("quitting...")


events.init_command_line_parser += on_init_command_line_parser
events.init += on_init
events.test_start += on_test_start
events.start_complete += on_start_complete
events.stats_request += on_stats_request
events.user_error += on_user_error
events.worker_report += on_worker_report
events.test_stop += on_test_stop
events.quitting += on_quitting


class TestUser(AsyncHttpUser):
    host = "https://httpbin.org"

    async def test_post(self):
        url="/post"
        async with self.session.post(url=url) as resp:
            data = await resp.json()
    
    async def test_get(self):
        url = "/get"
        async with self.session.get(url=url) as resp:
            data = await resp.text()
   

