#!python
# coding=utf-8
import logging, platform
from . import config, serve, __version__
from .log import logger

if __name__=='__main__':
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    logger.info('HTTP Server v%s/%s %s - by Gerald'
            % (__version__, platform.python_implementation(), platform.python_version()))
    config.add_gzip(['text/html', 'text/css', 'application/javascript'])
    server = config.add_server(port = 8000)
    server.add_alias('/', '~/')
    serve()
