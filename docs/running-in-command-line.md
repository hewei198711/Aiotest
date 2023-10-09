## Running In Command Line
**Stand-alone load test**
```console
aiotest -f aiotestfile.py -u 100 -r 10 -t 1800  -L DEBUG --logfile logs/aiotest.log
```
**`-u --users`**

Number of concurrent users

**`-r --rate`**

The rate per second in which users are started/stoped

**`-t --run-time`**

Stop after the specified amount of time, e.g. (300s, 20m, 3h, 1h30m, etc.)

**`-L --loglevel`**

Choose between DEBUG/INFO/WARNING/ERROR/CRITICAL. Default is INFO.

**`--logfile`**

Path to log file. If not set, log will go to stdout/stderr