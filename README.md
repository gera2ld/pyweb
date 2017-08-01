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
CLI usage:
```
usage: python3 -m httpd [-h] [-b BIND] [-r ROOT]

HTTP server by Gerald.

optional arguments:
  -h, --help            show this help message and exit
  -b BIND, --bind BIND  the address to bind, default as `:8000`
  -r ROOT, --root ROOT  the root directory of documents
```

Programmatic usage:
``` python
from httpd.server import HTTPDaemon

# Options are optional
server = HTTPDaemon({
    'host': '',
    'port': 80,
    'match': None,
    'handler': [
        {
            'handler': 'fcgi',
            'options': {
                'fcgi_ext': '.php',
                'fcgi_target': ['127.0.0.1:9000'],
                'index': [
                    'index.php',
                ],
            },
        },
        'file',
        'dir',
    ],
    'gzip': [
        'text/html',
        'text/css',
        'application/javascript',
    ],
    'options': {
        'root': '.',
        'index': [
            'index.html',
        ],
    },
})
server.serve()
```
