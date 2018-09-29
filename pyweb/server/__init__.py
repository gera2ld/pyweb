import asyncio
from pyserve import serve_forever
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
        serve_forever(self.servers, loop)
