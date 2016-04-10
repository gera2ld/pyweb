Super Light HTTP Daemon
===
This is a super light HTTP daemon based on `asyncio` (requires Python 3.5+).

Installation
---
``` sh
$ pip3 install git+https://github.com/gera2ld/pyhttpd.git
# Or install from source code
$ pip3 install ./path/to/pyhttpd
```

Usage
---
``` sh
$ python -m httpd -p 8000 -r ./
```
or use a python script:
``` python
from httpd import config, serve

server = config.add_server(port = 80)
server.add_rewrite('.*', '/index.php')
server.add_alias('/', 'htdocs/')
server.add_fastcgi(r'\.php$', [('127.0.0.1', 9000), ('127.0.0.1', 9001)], ['index.php'])
serve()
```
