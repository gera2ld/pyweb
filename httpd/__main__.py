#!python
# coding=utf-8
import logging, asyncio, platform
from . import httpd, config, serve
from .log import logger
__version__ = '1.0'

if __name__=='__main__':
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    logger.info('HTTP Server v%s/%s %s - by Gerald'
            % (__version__, platform.python_implementation(), platform.python_version()))
    loop = asyncio.get_event_loop()
    config.add_gzip(['text/html', 'text/css', 'application/javascript'])
    server = config.add_server(port = 8000)
    server.add_alias('/', '~/')
    serve()
