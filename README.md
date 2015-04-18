Gerald's HTTP Daemon
===
This is a light HTTP daemon built on `asyncio` (requires Python 3.4+).

Installation
---
``` sh
$ python setup.py install
```
or just copy `httpd` to your project.

Usage
---
Config files (`httpd.conf` and `mime.conf`) should be put in `~/.gerald` first.

```sh
$ python -m httpd
```
