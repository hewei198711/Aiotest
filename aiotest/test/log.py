# coding: utf-8

import sys

from loguru import logger

from aiotest.test.setting import LEVEL

logger.remove()
logger.add(sys.stderr, level=LEVEL)
logger.add("aiotest/test/log.log", level=LEVEL, retention="1 days")
