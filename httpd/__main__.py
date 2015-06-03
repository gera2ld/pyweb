#!python
# coding=utf-8
import logging,asyncio,platform
from . import httpd,httpconf
from .log import logger

if __name__=='__main__':
	logger.setLevel(logging.DEBUG)
	ch=logging.StreamHandler()
	ch.setLevel(logging.DEBUG)
	fmt=logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
	ch.setFormatter(fmt)
	logger.addHandler(ch)
	logger.info('HTTP Server v1/%s %s - by Gerald'
			% (platform.python_implementation(),platform.python_version()))
	loop=asyncio.get_event_loop()
	conf=httpconf.Config()
	for port in conf.conf:
		s=conf.get_conf(port)
		coro=asyncio.start_server(httpd.HTTPHandler,s.get('ip'),s.get('port'),loop=loop)
		server=loop.run_until_complete(coro)
		server.conf=s
		server.mimetypes=conf.mimetypes
		for s in server.sockets:
			logger.info('Serving on %s, port %d',*s.getsockname()[:2])
	loop.run_forever()
