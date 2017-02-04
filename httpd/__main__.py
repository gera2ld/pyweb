import logging, platform
from . import __version__
from .server import serve
from .config import Config
from .log import logger

import argparse, sys
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
ch.setFormatter(fmt)
logger.addHandler(ch)

parser = argparse.ArgumentParser(description='HTTP server by Gerald.')
parser.add_argument('-p', '--port', default=8000, help='the port for the server to bind')
parser.add_argument('-r', '--root', default='.', help='the root directory of documents')
args = parser.parse_args()

logger.info('HTTP Server v%s/%s %s - by Gerald'
        % (__version__, platform.python_implementation(), platform.python_version()))
config = Config()
config.add_gzip(['text/html', 'text/css', 'application/javascript'])
server = config.add_server(port=args.port)
server.add_alias('/', args.root)
serve(config)
