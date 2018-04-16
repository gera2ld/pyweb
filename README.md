pyweb
===
This is a super light web server based on `asyncio` (requires Python 3.5+).

Installation
---
``` sh
$ pip3 install git+https://github.com/gera2ld/pyweb.git
```

Usage
---
CLI usage:
```
Usage: pyweb [OPTIONS]

  Start a web server with pyweb.

Options:
  -b, --bind TEXT  the address to bind, default as `:4000`
  -r, --root TEXT  the root directory of documents
  --help           Show this message and exit.
```

Programmatic usage:
``` python
from pyweb.server import HTTPDaemon

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
