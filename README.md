# redis-look

```
Usage:
  redis-look-monitor.py
    --host,-h <host>                      (default: localhost)
    --port,-p <port>                      (default: 6379)
    --estimate-throughput,-e              (default: false)
    --estimate-throughput-limit,-l <num>  (default: 1000)
    --input-file <filename>               (default: None)
    --summary-number,-n <num>             (default: 5)
```
By default, the tool will connect to Redis and run `MONITOR` until `Ctrl-C` is pressed. It will then output the top operations for various dimensions. Note: `MONITOR` will negatively affect overall throughput, take care in production.

If `--estimate-throughput` is set, the tool will take the output from `MONITOR` and query `DEBUG OBJECT` for the top `<limit>` keys to get the serialized length. It will take the length returned and multiply it by the number of times accessed to get a rough estimate of the throughput required to service a key. Currently, the tool is not read/write aware, and it does not handle `MGET` properly which will affect the accuracy of the estimate.


Example

```
pip install requirements.txt
./redis-look-monitor.py -e
Connecting...
Issuing MONITOR...
Reading commands... 982 
^C 982 commands in 4.09 seconds (240.37 cmd/s) across 743 unique keys

* top by key

     count       avg/s      %  key
        32        7.83    3.3  _lock
         3        0.73    0.3  __raw__327
         3        0.73    0.3  __raw__553
         3        0.73    0.3  __raw__334
         3        0.73    0.3  __raw__113

* top by command

     count       avg/s      %  command
       636      155.68   64.8  SETEX
       104       25.46   10.6  LTRIM
       104       25.46   10.6  EXPIRE
       104       25.46   10.6  LPUSH
        32        7.83    3.3  EXISTS

* top by command and key

     count       avg/s      %  command and key
        32        7.83    3.3  EXISTS last_113
         1        0.24    0.1  SETEX last_999
         1        0.24    0.1  SETEX last_596
         1        0.24    0.1  LTRIM __raw__596
         1        0.24    0.1  SETEX __raw__621

Estimating throughput requirements for top 1000 keys...
* top by est. throughput

 est. bytes       count  throughput  throughput/s  key
       1.0M           3        3.0M          0.8K  __raw__222
       3.3K           3       10.0K          2.4K  __raw__103
       3.3K           3       10.0K          2.4K  __raw__990
       3.1K           3        9.4K          2.3K  __raw__327
       3.1K           3        9.4K          2.3K  __raw__553
```

TODO: 
 - create module and upload to PyPI
 - fix various code TODOs
 - upload 
