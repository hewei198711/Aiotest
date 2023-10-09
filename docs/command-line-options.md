## Command Line Options
Aiotest is configured mainly through command line arguments.
```console
aiotest --help

usage: aiotest [options] [-h] [-f AIOTESTFILE] [-H HOST] [--master] [--worker] [--expect-workers EXPECT_WORKERS] [--master-host MASTER_HOST] [--master-port MASTER_PORT]
                         [--master-bind-host MASTER_BIND_HOST] [--master-bind-port MASTER_BIND_PORT] [-u NUM_USERS] [-r RATE] [-t RUN_TIME] [--prometheus-port PROMETHEUS_PORT] [-b [BUCKETS ...]]
                         [--loglevel LOGLEVEL] [--logfile LOGFILE] [--show-users-wight] [-V]

asyncio is an easy to use, scriptable and scalable performance testing tool

options:
  -h, --help            show this help message and exit
  -f AIOTESTFILE, --aiotestfile AIOTESTFILE
                        Python module file to import, e.g. '../other.py'. Default: aiotestfile
  -H HOST, --host HOST  Host to load test in the following format: http://10.21.32.33
  --master              Set aiotest to run in distributed mode with this process as master
  --worker              Set aiotest to run in distributed mode with this process as worker
  --expect-workers EXPECT_WORKERS
                        How many workers master should expect to connect before starting the test
  --master-host MASTER_HOST
                        Host or IP address of aiotest master for distributed load testing. Only used when running with --worker. Defaults to 127.0.0.1.
  --master-port MASTER_PORT
                        The port to connect to that is used by the aiotest master for distributed load testing. Only used when running with --worker. Defaults to 5557. Note that workers will also connect
                        to the master node on this port + 1.
  --master-bind-host MASTER_BIND_HOST
                        Interfaces (hostname, ip) that aiotest master should bind to. Only used when running with --master. Defaults to * (all available interfaces).
  --master-bind-port MASTER_BIND_PORT
                        Port that worker master should bind to. Only used when running with --master. Defaults to 5557. Note that aiotest will also use this port + 1, so by default the master node will
                        bind to 5557 and 5558.
  -u NUM_USERS, --users NUM_USERS
                        Number of concurrent users
  -r RATE, --rate RATE  The rate per second in which users are started/stoped
  -t RUN_TIME, --run-time RUN_TIME
                        Stop after the specified amount of time, e.g. (300s, 20m, 3h, 1h30m, etc.). Only used together with --no-web
  --prometheus-port PROMETHEUS_PORT
                        Port that metrics are exposed over HTTP, to be read by the Prometheus server.
  -b [BUCKETS ...], --buckets [BUCKETS ...]
                        Prometheus histogram buckets
  --loglevel LOGLEVEL, -L LOGLEVEL
                        Choose between DEBUG/INFO/WARNING/ERROR/CRITICAL. Default is INFO.
  --logfile LOGFILE     Path to log file. If not set, log will go to stdout/stderr
  --show-users-wight    print json data of the users classes' execution wight
  -V, --version         show program's version number and exit
```
