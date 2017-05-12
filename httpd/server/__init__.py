import os
import asyncio
from .. import httpd
from ..utils import logger
from .base import Config

class HTTPServer(Config):
    def __init__(self, *k, loop=None, **kw):
        super().__init__(*k, **kw)
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.started = None

    async def _start(self):
        async def handle(reader, writer):
            handler = httpd.HTTPHandler(reader, writer, self)
            await handler.handle()
        self._server = await asyncio.start_server(handle, self.host, self.port, loop=self.loop)
        self.hostnames = (sock.getsockname() for sock in self._server.sockets)

    def start(self):
        if not self.started:
            self.started = asyncio.ensure_future(self._start())
        return self.started

    @staticmethod
    def serve(servers, loop=None):
        if isinstance(servers, HTTPServer):
            servers = [servers]
        if loop is None:
            loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*(
            server.start() for server in servers)))
        for server in servers:
            for hostname in server.hostnames:
                logger.info('Serving on %s, port %d', *hostname[:2])
        if os.name == 'nt':
            def wake_up_later():
                loop.call_later(.1, wake_up_later)
            wake_up_later()
        loop.run_forever()
