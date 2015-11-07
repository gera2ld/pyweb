#!python
# coding=utf-8
# Reference: http://www.w3.org/Protocols/rfc2616/rfc2616.html
import asyncio
from . import config, httpd
from .log import logger
__version__ = '1.0'
__author__ = 'Gerald <i@gerald.top>'

def serve():
    loop = asyncio.get_event_loop()
    for port in config.servers:
        coro = asyncio.start_server(httpd.HTTPHandler, '', port, loop = loop)
        server = loop.run_until_complete(coro)
        for sock in server.sockets:
            logger.info('Serving on %s, port %d', *sock.getsockname()[:2])
    loop.run_forever()

