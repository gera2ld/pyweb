import os
import asyncio
from ..utils import logger
from .context import HTTPContext
from .matcher import normalize_config

class HTTPDaemon:
    def __init__(self, config, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.config = normalize_config(config)
        self.servers = []
        logger.debug('%s', self.config)

    async def start_server(self, config_item):
        async def handle(reader, writer):
            handler = HTTPContext(reader, writer, config_item)
            await handler.handle()
        host = config_item.get('host', '')
        port = config_item.get('port', 80)
        server = await asyncio.start_server(handle, host, port, loop=self.loop)
        self.servers.append(server)

    async def start_servers(self):
        await asyncio.gather(*(self.start_server(item) for item in self.config))

    def serve(self):
        loop = self.loop
        if loop is None:
            loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start_servers())
        for server in self.servers:
            for sock in server.sockets:
                hostname = sock.getsockname()
                logger.info('Serving on %s, port %d', *hostname[:2])
        if os.name == 'nt':
            def wake_up_later():
                loop.call_later(.1, wake_up_later)
            wake_up_later()
        loop.run_forever()
