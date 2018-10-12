# -*- coding: utf-8 -*-

"""Console script for pyweb."""
import sys
import platform
import click
from . import __version__
from .server import HTTPDaemon
from .utils import logger, parse_addr


@click.command()
@click.option('-b', '--bind', default=':4000', help='the address to bind, default as `:4000`')
@click.option('-r', '--root', default='.', help='the root directory of documents')
def main(bind, root):
    """Start a web server with pyweb."""
    host, port = parse_addr(bind, default=('', 4000))
    logger.info(
        'HTTP Server v%s/%s %s - by Gerald',
        __version__, platform.python_implementation(), platform.python_version())
    server = HTTPDaemon({
        'host': host,
        'port': port,
        'match': None,
        'handler': [
            'proxy',
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
            'root': root,
            'index': [
                'index.html',
            ],
        },
    })
    server.serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
