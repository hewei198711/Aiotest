# encoding: utf-8

import asyncio
import re
import os
import sys
import inspect
import argparse
import importlib
from datetime import timedelta
from pprint import pprint

import aiotest
from prometheus_client import Histogram
from aiotest import stats_exporter
from aiotest.stats_exporter import STATSERROR
from aiotest.log import logger, setup_logging
from aiotest.shape import LoadUserShape
from aiotest.user import User
from aiotest import events
from aiotest import runners
from aiotest.runners import LocalRunner, MasterRunner, WorkerRunner


version = aiotest.__version__

async def parse_options(args=None):
    """
    Handle command-line options with argparse.ArgumentParser.

    Return list of arguments, largely for use in `parse_arguments`.
    """

    # Initialize
    parser = argparse.ArgumentParser(
        prog="aiotest [options]", 
        description="asyncio is an easy to use, scriptable and scalable performance testing tool"
    )

    parser.add_argument(
        '-f', '--aiotestfile',
        default='aiotestfile',
        help="Python module file to import, e.g. '../other.py'. Default: aiotestfile"
    )
        
    parser.add_argument(
        '-H', '--host',
        default= "",
        help="Host to load test in the following format: http://10.21.32.33"
    )
    
    # master-worker
    parser.add_argument(
        '--master',
        action='store_true',
        help="Set aiotest to run in distributed mode with this process as master"
    )

    parser.add_argument(
        '--worker',
        action='store_true',
        help="Set aiotest to run in distributed mode with this process as worker"
    )

    parser.add_argument(
        '--expect-workers',
        type=int,
        default=1,
        help="How many workers master should expect to connect before starting the test"
    )
        
    parser.add_argument(
        '--master-host',
        default="127.0.0.1",
        help="Host or IP address of aiotest master for distributed load testing. Only used when running with --worker. Defaults to 127.0.0.1."
    )
    
    parser.add_argument(
        '--master-port',
        type=int,
        default=5557,
        help="The port to connect to that is used by the aiotest master for distributed load testing. Only used when running with --worker. Defaults to 5557. Note that workers will also connect to the master node on this port + 1."
    )

    parser.add_argument(
        '--master-bind-host',
        default="*",
        help="Interfaces (hostname, ip) that aiotest master should bind to. Only used when running with --master. Defaults to * (all available interfaces)."
    )
    
    parser.add_argument(
        '--master-bind-port',
        type=int,
        default=5557,
        help="Port that worker master should bind to. Only used when running with --master. Defaults to 5557. Note that aiotest will also use this port + 1, so by default the master node will bind to 5557 and 5558."
    )

    # users rate run_time
    parser.add_argument(
        '-u', '--users',
        type=int,
        dest='num_users',
        default=1,
        help="Number of concurrent users"
    )

    parser.add_argument(
        '-r', '--rate',
        type=int,
        default=1,
        help="The rate per second in which users are started/stoped"
    )

    parser.add_argument(
        '-t', '--run-time',
        type=str,
        default=None,
        help="Stop after the specified amount of time, e.g. (300s, 20m, 3h, 1h30m, etc.)"
    )    

    # prometheus
    parser.add_argument(
        '--prometheus-port',
        type=int,
        default=8089,
        help="Port that metrics are exposed over HTTP, to be read by the Prometheus server."
    )
    
    parser.add_argument(
        '-b', '--buckets', 
        type=int, nargs='*', 
        default= [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 2000, 5000, 8000], 
        help='Prometheus histogram buckets'
    )    
    
    # loglevel logfile
    parser.add_argument(
        '--loglevel', '-L',
        default='INFO',
        help="Choose between DEBUG/INFO/WARNING/ERROR/CRITICAL. Default is INFO.",
    )
    
    parser.add_argument(
        '--logfile',
        default = None,
        help="Path to log file. If not set, log will go to stdout/stderr",
    )
    
    # show 
    parser.add_argument(
        '--show-users-wight',
        action='store_true',
        help="print json data of the users classes' execution wight"
    )
    
    parser.add_argument(
        '-V', '--version',
        action='version',
        version= f'aiotest=={version}',
    )

    # Provides a hook to add command-line arguments
    await events.init_command_line_parser.fire(parser=parser)
   
    return parser.parse_args(args=args)

def find_aiotestfile(aiotestfile):
    """
    Attempt to locate a aiotestfile by either explicitly.
    """
    _, suffix = os.path.splitext(aiotestfile)
    if suffix and suffix != ".py":
        logger.warning(f"{aiotestfile} mast be .py file")
        sys.exit(1)
    if not suffix:
        aiotestfile += ".py"
    # return abspath
    if os.path.dirname(aiotestfile):
        # expand home-directory markers and test for existence
        expanded = os.path.expanduser(aiotestfile)
        if os.path.exists(expanded):
            return os.path.abspath(expanded)
    else:
        path = os.path.abspath(".")
        joined = os.path.join(path, aiotestfile)
        if os.path.exists(joined):
            return os.path.abspath(joined)
    
    logger.warning(f"Current working directory:{os.path.abspath('.')}，File not found:{aiotestfile}")

def is_shape_class(cls):
    "Check if a class is a SubLoadUserShape"
    return bool(
        inspect.isclass(cls)
        and issubclass(cls, LoadUserShape)
        and (cls.__name__.startswith("Test") or cls.__name__.endswith("Test"))
        and cls.__dict__["__module__"] != "aiotest.shape"
    )

def is_user_class(cls):
    """
    Check if a variable is a runnable (non-abstract) SubUser class
    """
    return bool(
        inspect.isclass(cls)
        and issubclass(cls, User)
        and getattr(cls, "weight")
        and (cls.__name__.startswith("Test") or cls.__name__.endswith("Test"))
        and cls.__dict__["__module__"] != "aiotest.user"
        )

def load_aiotestfile(path):
    """
    Import given aiotestfile path and return (UserClass, LoadUserShapeClass).
    """
    # Start with making sure the current working dir is in the sys.path
    sys.path.insert(0, os.getcwd())
    directory, aiotestfile = os.path.split(path)
    # If the directory isn't in the PYTHONPATH, add it so our import will work
    added_to_path = False
    index = None
    if directory not in sys.path:
        sys.path.insert(0, directory)
        added_to_path = True
    # If the directory IS in the PYTHONPATH, move it to the front temporarily,
    # otherwise other aiotestfiles -- like Aiotest's own -- may scoop the intended one.
    else:
        i = sys.path.index(directory)
        if i != 0:
            index = i
            # Add to front, then remove from original position
            sys.path.insert(0, directory)
            del sys.path[i+1]

    imported = importlib.import_module(os.path.splitext(aiotestfile)[0])
    # Remove directory from path if we added it ourselves (just to be neat)
    if added_to_path:
        del sys.path[0]
    # Put back in original index if we moved it
    if index:
        del sys.path[0]
        sys.path.insert(index, directory)
    # Return our two-tuple
    user_classes = {name: value for name, value in vars(imported).items() if is_user_class(value)}
    # Find shape class, if any, return it
    shape_classes = [value for value in vars(imported).values() if is_shape_class(value)]
    if len(shape_classes) == 1:
        shape_class = shape_classes[0]()
    elif len(shape_classes) > 1:
        logger.error("tactics class  only have one!!")
        sys.exit(1)
    else:
        shape_class = None
    return user_classes, shape_class

def parse_timespan(time_str):
    """
    Parse a string representing a time span and return the number of seconds.
    Valid formats are: 20, 20s, 3m, 2h, 1h20m, 3h30m10s, etc.
    """
    if not time_str:
        raise ValueError("Invalid time span format")
    
    if re.match(r"^\d+$", time_str):
        # if an int is specified we assume they want seconds
        return int(time_str)
    
    timespan_regex = re.compile(r"((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?")
    parts = timespan_regex.match(time_str)
    if not parts:
        raise ValueError("Invalid time span format. Valid formats: 20, 20s, 3m, 2h, 1h20m, 3h30m10s, etc")
    parts = parts.groupdict() # {'hours': '3', 'minutes': '30', 'seconds': '10'}, {'hours': None, 'minutes': None, 'seconds': '20'}
    time_params = {name:int(value) for name, value in parts.items() if value}
    if not time_params:
        raise ValueError("Invalid time span format. Valid formats: 20, 20s, 3m, 2h, 1h20m, 3h30m10s, etc")
    return int(timedelta(**time_params).total_seconds())


async def main():
    options = await parse_options()
    
    loglevel = options.loglevel.upper()
    if loglevel in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        logfile = options.logfile
        if logfile:
            setup_logging(loglevel, logfile)
        else:
            setup_logging(loglevel, None)
    else:
        logger.warning("Invalid --loglevel. Valid values are: DEBUG/INFO/WARNING/ERROR/CRITICAL")
        sys.exit(1)
    
    aiotestfile = find_aiotestfile(options.aiotestfile)
    if not aiotestfile:
        logger.warning("Could not find any Aiotestfile! Ensure file ends in '.py' and see --help for available options.")
        sys.exit(1)
    
    num_users = options.num_users
    if not isinstance(num_users, int) or num_users <= 0:
        logger.warning(f"{options.num_users} mast be int type and >= 1")  
        sys.exit(1)
    
    rate = options.rate
    if not isinstance(rate, int) or rate <= 0 or rate > num_users:
        logger.warning(f"{options.rate} mast be int type and >= 1, and mast <= num_users")  
        sys.exit(1)
    
    user_classes, shape_class = load_aiotestfile(aiotestfile)
    if not user_classes:
        logger.warning("No User class found!")
        sys.exit(1)
    user_classes = list(user_classes.values())
    
    if os.name != "nt" and not options.master:
        try:
            import resource
            if resource.getrlimit(resource.RLIMIT_NOFILE)[0] < 10000:
                # Increasing the limit to 10000 within a running process should work on at least MacOS.
                # It does not work on all OS:es, but we should be no worse off for trying.
                resource.setrlimit(resource.RLIMIT_NOFILE, [10000, resource.RLIM_INFINITY])
        except BaseException:
            logger.warning(
                """
                System open file limit '10000' is below minimum setting '10000'. 
                It's not high enough for load testing, and the OS didn't allow aiotest to increase it by itself. 
                """
            )    
   
    if shape_class and (num_users or rate or options.run_time):
        logger.warning("aiotestfile contains the LoadUserShape subclass, which ignores arguments specified on the command line :users or rate or run_time.")
        options.run_time = None

    if options.show_users_wight:
        user_wight = {}
        for user in user_classes:
            user_wight[user.__name__] = user.weight
        pprint(user_wight)
        sys.exit(0)

    if options.run_time and not shape_class:
        if options.worker:
            logger.error("--run-time should be specified on the master node, and not on worker nodes")
            sys.exit(1)
        try:
            options.run_time = parse_timespan(options.run_time)
        except ValueError:
            logger.error("Valid --run-time formats are: 20, 20s, 3m, 2h, 1h20m, 3h30m10s, etc.")
            sys.exit(1)
    
    options.buckets = sorted(set(options.buckets))
    options.buckets.append(float('inf'))
    stats_exporter.aiotest_response_times = Histogram(name='aiotest_response_times', documentation='aiotest response times', labelnames=["name", "method", "code"], buckets=tuple(options.buckets))
    
    if options.master:
        runners.global_runner = MasterRunner(user_classes, shape_class, options)
        while len(runners.global_runner.workers.ready) < options.expect_workers:
            logger.info(f"Waiting for workers to be ready, {len(runners.global_runner.workers.ready)} of {options.expect_workers} connected")
            await asyncio.sleep(2)     
    elif options.worker:
        runners.global_runner = WorkerRunner(user_classes, shape_class, options)   
    else:
        runners.global_runner = LocalRunner(user_classes, shape_class, options)
    
    await events.init.fire()
               
    try:
        if not options.worker:           
            async with asyncio.timeout(options.run_time):
                if shape_class:
                    runners.global_runner.start_shape()
                else:
                    await runners.global_runner.start(num_users, rate)
                            
                await asyncio.sleep(1)
                for task in runners.global_runner.tasks:
                    await task
        else:
            await asyncio.sleep(1)
            for task in runners.global_runner.tasks:
                await task 
    except (TimeoutError, KeyboardInterrupt, asyncio.CancelledError):
        await runners.global_runner.quit()
        await asyncio.sleep(0.2)
        if STATSERROR:
            for k, e in STATSERROR.items():
                logger.error(f"{k}:{e}")
            sys.exit(1)
        else:
            sys.exit(0)


def run():
    if sys.platform != "win32": 
        import uvloop
        uvloop.install()

    asyncio.run(main())






