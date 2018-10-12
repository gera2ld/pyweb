import asyncio
from urllib import parse
from .base import BaseHandler
from ..utils import errors

__all__ = ['ProxyHandler']

BUF_SIZE = 8192

class ConnectProtocol(asyncio.Protocol):
    def __init__(self, writer):
        self.writer = writer

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        if self.writer:
            self.writer = None

    def data_received(self, data):
        self.writer.write(data, True)

class ProxyHandler(BaseHandler):
    async def __call__(self, context, options):
        if context.request.method == 'CONNECT':
            return await self.handle_connect(context, options)
        if '://' in context.request.path:
            return await self.handle_proxy(context, options)

    async def handle_connect(self, context, options):
        context.write(None)
        host, _, port = context.request.path.partition(':')
        port = int(port)
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_connection(lambda : ConnectProtocol(context), host, port)
        while True:
            data = await context.reader.read(BUF_SIZE)
            if not data:
                break
            transport.write(data)
        transport.close()
        return True

    async def handle_proxy(self, context, options):
        raise errors.HTTPError(501)
