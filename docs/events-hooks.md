## Event hooks
Aiotest comes with a number of event hooks that can be used to extend Aiotest in different ways.

For example, here’s how to set up an event listener that will trigger after a request is completed:
```python
from aiotest import AsyncHttpUser, events

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

events.stats_request += on_stats_request  
```
**`events.init_command_line_parser`**

Event that can be used to add command line options to Aiotest


**`events.init`**

Called when initializing runner

**`events.test_start`**

Fired on each node when a new load test is started. It's not fired again if the number of users change during a test.

**`events.stats_request`**

Fired when a request in completed, successful or unsuccessful. This event is typically used to report requests when writing custom clients for aiotest.

**`events.user_error`**

Fired when an exception occurs inside the execution of a User class.

**`events.worker_report`**

Used when Aiotest is running in --master mode and is fired when the master
server receives a report from a Aiotest worker server.

This event can be used to aggregate data from the Aiotest worker servers.

**`events.test_stop`**

Fired on each node when a load test is stopped.

**`events.quitting`**

Fired after quitting events, just before process is exited.

see more [Events](https://github.com/hewei198711/Aiotest/blob/main/examples/add_events.py)