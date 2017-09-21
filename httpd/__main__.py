'''
Main script to start a server.
'''
import platform
import argparse
from . import __version__
from .server import HTTPDaemon
from .utils import logger, parse_addr

def main():
    '''Start server.'''
    parser = argparse.ArgumentParser(prog='python3 -m httpd', description='HTTP server by Gerald.')
    parser.add_argument(
        '-b', '--bind', default=':4000',
        help='the address to bind, default as `:4000`')
    parser.add_argument(
        '-r', '--root', default='.',
        help='the root directory of documents')
    args = parser.parse_args()

    logger.info(
        'HTTP Server v%s/%s %s - by Gerald',
        __version__, platform.python_implementation(), platform.python_version())

    host, port = parse_addr(args.bind, default_host='', default_port=4000)
    server = HTTPDaemon({
        'host': host,
        'port': port,
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
            'root': args.root,
            'index': [
                'index.html',
            ],
        },
    })
    server.serve()

if __name__ == '__main__':
    main()
