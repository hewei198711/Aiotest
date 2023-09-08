# encoding: utf8

import sys
import asyncio
from aiotest.main import main


if sys.platform == "win32": 
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
else:
    import uvloop
    uvloop.install()


asyncio.run(main())
