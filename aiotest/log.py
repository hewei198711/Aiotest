# encoding: utf-8

import sys

from loguru import logger


def setup_logging(loglevel, logfile=None):
    loglevel = loglevel.upper()
    logger.remove()
    logger.add(sys.stderr, level=loglevel)
    if logfile:
        logger.add(logfile, level=loglevel, retention="1 days")