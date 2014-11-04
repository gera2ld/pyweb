#!python
# coding=utf-8
import logging,asyncio,platform
from . import httpd,httpconf

if __name__=='__main__':
	logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s: %(message)s')
	logging.info('HTTP Server v1/%s %s - by Gerald'
			% (platform.python_implementation(),platform.python_version()))
	loop=asyncio.get_event_loop()
	conf=httpconf.Config('~/.gerald/mime.conf','~/.gerald/httpd.conf')
	for port in conf.conf:
		s=conf.get_conf(port)
		host,_,port=s.get('server').partition(':')
		coro=asyncio.start_server(httpd.HTTPHandler,host,port,loop=loop)
		server=loop.run_until_complete(coro)
		server.conf=s
		server.mime=conf.mime
		server.fcgi_handlers=conf.fcgi_handlers
		for s in server.sockets:
			logging.info('Serving on %s, port %d',*s.getsockname()[:2])
	loop.run_forever()
