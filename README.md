# YAWFA — Yet Another Wrapper for `argparse`

**YAWFA** is a declarative, type-safe wrapper around Python's `argparse` module.

Copyright 2026 Ian Pilcher <<arequipeno@gmail.com>>

## Overview

Python's `argparse` module is very capable, but it suffers from a couple of
pretty serious issues.

1. It's API is entirely imperative.  Configuring a parser requires a series of
   calls to `ArgumentParser.add_argument` and other methods.  The signature of
   `ArgumentParser.add_argument` is also confusing; it isn't clear how the
   various arguments interact and conflict.

2. It doesn't support type hinting at all.  Static type checkers like **Mypy**
   have no visibility of the attributes that `ArgumentParser.parse_args` adds
   to the namespace objects that it returns, so they will complain about every
   use of these attributes.

**YAWFA** addresses these issues by using type-hinted classes (similar to
`dataclasses`) to provide declarative parser configurations.  The attributes and
type hints in these classes ensure that type checkers are fully aware of the
attributes that are returned by the argument parser.

## Limitations

* **YAWFA** currently supports only a fraction of the full functionality of
  `argparse`.

* Python 3.14 or later is required.

* The API is very much in flux.

## Use

First, create a class that defines the arguments.

`test.py`:

```python
import uuid
import yawfa

class MyArgs(yawfa.Arguments, custom_types={"identifier": uuid.UUID}):

    logging = yawfa.group("Logging", "Options that control logging")
    log_dest = yawfa.mxgroup(group="logging")

    # Positional arguments.
    profile: uuid.UUID = yawfa.arg(
        type="identifier", positional=True, help="Connection profile UUID"
    )
    net_interface: str=yawfa.arg(
        positional=True, required=False, deprecated=True,
        help="Network interface name", metavar="netif"
    )

    # Options in the "logging" group.
    debug: bool=yawfa.arg(
        short="-d", group="logging", help="Log debug messages"
    )

    # These are in the "log_dest" mutual exclusion group, which is in the
    # logging group.
    syslog: bool=yawfa.arg(
        short="-l", group="log_dest", help="Log to syslog (not stderr)"
    )
    stderr: bool=yawfa.arg(
        short="-e", group="log_dest", help="Log to stderr (not syslog)"
    )

    # An option outside any group.
    thread_count: int=yawfa.arg(
        short="-t", default=1, metavar="COUNT",
        help="Number of worker threads (default 1)"
    )

    # Ignored by YAWFA.  Can be added later.
    post_processed: int


my_args = MyArgs.parse()
print(my_args)
```

Verify that the parser was configured correctly.

```
$ python3 test.py -h
usage: test.py [-h] [--debug] [--syslog | --stderr] [--thread-count COUNT] profile [netif]

positional arguments:
  profile               Connection profile UUID
  netif                 Network interface name

options:
  -h, --help            show this help message and exit
  --thread-count, -t COUNT
                        Number of worker threads (default 1)

Logging:
  Options that control logging

  --debug, -d           Log debug messages
  --syslog, -l          Log to syslog (not stderr)
  --stderr, -e          Log to stderr (not syslog)
```

Test it.

```
$ python3 -i test.py --debug --syslog --thread-count 12 0927d881-860d-4278-86e1-a2d6cc3fcc29 eth0
test.py: warning: argument 'net_interface' is deprecated
<__main__.MyArgs {profile: 0927d881-860d-4278-86e1-a2d6cc3fcc29, net_interface: eth0, debug: True, syslog: True, stderr: False, thread_count: 12}>
>>> my_args.debug
True
>>> my_args.thread_count
12
```




