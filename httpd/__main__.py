'''
Main script to start a server.
'''
import logging
import platform
import argparse
from . import __version__
from .server import HTTPServer
from .log import logger

def parse_addr(hostname, default_host='', default_port=80):
    if hostname.count(':') > 1:
        # IPv6
        if hostname.startswith('['):
            end_offset = hostname.index(']')
            host = hostname[1 : end_offset]
            port = hostname[end_offset + 1 :]
            if port:
                assert port.startswith(':')
                port = port[1:]
        else:
            host = hostname
            port = default_port
    else:
        # IPv4
        host, _, port = hostname.partition(':')
    try:
        port = int(port)
    except:
        port = default_port
    return host, port

def main():
    '''Start server.'''
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    parser = argparse.ArgumentParser(prog='python3 -m httpd', description='HTTP server by Gerald.')
    parser.add_argument(
        '-b', '--bind', default=':8000',
        help='the address to bind, default as `:8000`')
    parser.add_argument(
        '-r', '--root', default='.',
        help='the root directory of documents')
    args = parser.parse_args()

    logger.info(
        'HTTP Server v%s/%s %s - by Gerald',
        __version__, platform.python_implementation(), platform.python_version())

    host, port = parse_addr(args.bind, default_host='', default_port=8000)
    server = HTTPServer(host=host, port=port)
    server.add_gzip(['text/html', 'text/css', 'application/javascript'])
    server.add_alias('/', args.root)
    HTTPServer.serve(server)

if __name__ == '__main__':
    main()
