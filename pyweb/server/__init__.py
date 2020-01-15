import asyncio
from gera2ld.pyserve import start_server, serve_forever
from ..utils import logger
from .context import HTTPContext
from .matcher import normalize_config

class HTTPDaemon:
    def __init__(self, config):
        loop = asyncio.get_event_loop()
        self.config = normalize_config(config)
        self.servers = []
        logger.debug('%s', self.config)

    async def start_server(self, config_item):
        async def handle(reader, writer):
            handler = HTTPContext(reader, writer, config_item)
            await handler.handle()
        bind = config_item.get('bind', ':4000')
        server = await start_server(handle, bind)
        self.servers.append(server)

    async def start_servers(self):
        await asyncio.gather(*(self.start_server(item) for item in self.config))

    def serve(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start_servers())
        serve_forever(self.servers)
