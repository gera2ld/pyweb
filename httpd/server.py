import asyncio
from . import httpd
from .config import ServerConfig
from .log import logger

class HTTPServer:
    def __init__(self, config=None):
        if config is None:
            config = ServerConfig()
        self.config = config

    async def handle(self, reader, writer):
        handler = httpd.HTTPHandler(reader, writer, self.config)
        await handler.handle()

    async def serve(self):
        loop = asyncio.get_event_loop()
        self.server = await asyncio.start_server(self.handle, self.config.host, self.config.port, loop=loop)
        self.sockets = self.server.sockets

def serve(config):
    loop = asyncio.get_event_loop()
    for port in config.servers:
        port_config = config.get_server(port=port)
        server = HTTPServer(port_config)
        loop.run_until_complete(server.serve())
        for sock in server.sockets:
            logger.info('Serving on %s, port %d', *sock.getsockname()[:2])
    loop.run_forever()