Super Light HTTP Daemon
===
This is a super light HTTP daemon based on `asyncio` (requires Python 3.5+).

Installation
---
``` sh
$ pip3 install git+https://github.com/gera2ld/pyhttpd.git
```

Usage
---
Command line usage:
``` sh
$ python3 -m httpd -p 8000 -r ./
```

Programmatic usage:
``` python
# 1. Build server

from httpd import HTTPServer

server = HTTPServer(port=80)
server.add_rewrite('.*', '/index.php')
server.add_alias('/', 'htdocs/')
server.add_fastcgi(r'\.php$', [('127.0.0.1', 9000), ('127.0.0.1', 9001)], ['index.php'])

# 2. start server

#   - the quick way
HTTPServer.serve(server)

#   - or start manually
import asyncio

server.start()
asyncio.get_event_loop().run_forever()
```
