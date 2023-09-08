# encoding: utf-8

import sys
import traceback
from aiotest.log import logger


class EventHook:
    
    def __init__(self):
        self._handlers = []
    
    def __iadd__(self, handler):
        self._handlers.append(handler)
        return self
    
    def __isub__(self, handler):
        self._handlers.remove(handler)
        return self
    
    async def fire(self, **kwargs):

        for handler in self._handlers:
            try:
                await handler(**kwargs)
            except Exception as e:
                logger.error(f"{sys.exc_info()[0].__name__}: {e}" + "".join(traceback.format_tb(sys.exc_info()[2])).strip())

init_command_line_parser = EventHook()
init = EventHook()
test_start = EventHook()
start_complete = EventHook()
stats_request = EventHook()
user_error = EventHook()
worker_report = EventHook()
test_stop = EventHook()
quitting = EventHook()

