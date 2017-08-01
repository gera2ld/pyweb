import sys
import asyncio
import http.client
import http.server
import logging
from .. import __version__
from ..utils import logger, writers, errors, time_utils, template
from .request import Request
from .matcher import iter_handlers

DEFAULTS = {
    'protocol_version': (1, 1),
}

class HTTPContext:
    server_version = 'SLHD/' + __version__
    sys_version = 'Python/' + sys.version.split()[0]
    version_string = server_version + ' ' + sys_version
    protocol_version = DEFAULTS['protocol_version']
    # responses is a dict of {status_code: (short_reason, empty_str_or_long_reason)}
    responses = http.server.BaseHTTPRequestHandler.responses.copy()
    # handler_classes = [
    #     handlers.FCGIHandler,
    #     handlers.FileHandler,
    #     handlers.DirectoryHandler,
    #     handlers.NotFoundHandler,
    # ]
    def __init__(self, reader, writer, config):
        self.reader = reader
        self.writer = writer
        self.remote_addr = writer.get_extra_info('peername')
        self.local_addr = writer.get_extra_info('sockname')
        self.config = config
        self.logger = logger
        self.keep_alive = True
        self.logger.setLevel(config.get('loglevel', logging.INFO))
        env = self.base_environ = {}
        env['GATEWAY_INTERFACE'] = 'CGI/1.1'
        env['SERVER_ADDR'] = self.local_addr[0]
        env['SERVER_PORT'] = str(self.local_addr[1])
        env['REMOTE_ADDR'] = self.remote_addr[0]
        env['REMOTE_PORT'] = str(self.remote_addr[1])
        env['CONTENT_LENGTH'] = ''
        env['SCRIPT_NAME'] = ''
        self.clean()

    async def handle(self):
        while self.keep_alive:
            try:
                await self.handle_one_request()
            except (asyncio.TimeoutError, ConnectionError):
                break
            except:
                import traceback
                traceback.print_exc()
                break
            finally:
                if self.request and self.request.requestline:
                    written = self.raw_writer.written if self.raw_writer else '-'
                    self.logger.info('%s->%s "%s" %d %s',
                        self.env['REMOTE_ADDR'], self.env.get('HTTP_HOST', '-'),
                        self.request.requestline, self.status[0], written)
                self.clean()
        self.writer.close()

    async def handle_one_request(self):
        self.request = Request(self.reader, self.protocol_version, self.config.get('keep_alive_timeout', 120), self.env)
        try:
            assert await self.request.parse()
        except errors.HTTPError as e:
            print(e)
            self.send_error(e.status_code, e.long_msg)
            return
        except AssertionError:
            self.keep_alive = False
            return
        self.keep_alive = self.request.keep_alive
        self.headers = http.client.HTTPMessage()
        for handle, options in iter_handlers(self.request, self.config):
            self.logger.debug('get handler: %s, %s', handle, options)
            gen = await handle(self, options)
            if gen is True:
                self.write(None)
            elif gen:
                for chunk in gen:
                    self.write(chunk)
                    await self.writer.drain()
            if gen:
                break
        else:
            self.send_error(404)
        self.buffer.flush()
        self.buffer.close()
        await self.writer.drain()

    def send_response_only(self, code, message = None):
        """Send the response header only."""
        if message is None:
            if code in self.responses:
                message = self.responses[code][0]
            else:
                message = ''
        if self.request.protocol_version != (0, 9):
            header_lines = ['HTTP/%d.%d %d %s\r\n' % (*self.protocol_version, code, message)]
            for key, value in self.headers.items():
                header_lines.append('%s: %s\r\n' % (key, value))
            header_lines.append('\r\n')
            self.writer.writelines(line.encode('latin-1', 'strict') for line in header_lines)
        connection = self.headers.get('connection')
        if connection:
            connection = connection.lower();
            if connection == 'close':
                self.keep_alive = False
            elif connection == 'keep-alive':
                self.keep_alive = True

    def send_headers(self):
        if self.request.accept_encoding('gzip'):
            content_type = self.headers.get('content-type', '')
            gzip = self.config.get('gzip')
            if gzip and content_type in gzip:
                self.content_encoding = 'gzip'
        if self.request.protocol_version >= (1, 1):
            if not self.request.keep_alive:
                self.headers['connection'] = 'close'
            self.chunk_mode = True # only allowed in HTTP/1.1
            if self.status[0] in (204, 304):
                self.chunk_mode = False
            elif 'content-length' in self.headers:
                if self.content_encoding == 'deflate':
                    self.chunk_mode = False
                else:
                    del self.headers['content-length']
        else:
            if self.request.keep_alive:
                self.headers['connection'] = 'keep-alive'
            self.chunk_mode = False
        if self.content_encoding == 'gzip':
            self.headers['content-encoding'] = 'gzip'
        if self.chunk_mode:
            self.headers['transfer-encoding'] = 'chunked'
        self.headers.add_header('Server', self.version_string)
        self.headers.add_header('Date', time_utils.date_time_string())
        # send headers
        self.send_response_only(*self.status)
        self.headers_sent = True
        writer = self.raw_writer = writers.RawWriter(self.writer, self.logger)
        if self.chunk_mode:
            writer = writers.ChunkedWriter(writer, self.logger)
        writer = writers.BufferedWriter(writer, self.logger)
        if self.content_encoding == 'gzip':
            writer = writers.GZipWriter(writer, self.logger)
        self.buffer = writer

    def write(self, data):
        if not self.headers_sent:
            self.send_headers()
        if self.request.method != 'HEAD' and data:
            if isinstance(data, str):
                data = data.encode('utf-8', 'ignore')
            if data:
                self.buffer.write(data)

    def set_status(self, code=200, message=None):
        self.status = code, message

    def clean(self):
        self.set_status()
        self.env = self.base_environ.copy()
        self.request = None
        self.chunk_mode = False
        self.content_encoding = 'deflate'
        self.headers = None
        self.headers_sent = False
        self.buffer = None
        self.raw_writer = None

    def redirect(self, url, code = 303, message = None):
        if self.headers_sent:
            raise errors.HeadersSentError
        self.set_status(code)
        self.headers['Location'] = url
        if message is None:
            message = 'The URL has been moved <a href="%s">here</a>.' % url
        self.write(message)

    def send_error(self, code, message = None):
        if code >= 200 and code not in (204, 304):
            self.headers['content-type'] = 'text/html'
            if message is None:
                _, message = self.responses.get(code, (None, '???'))
            self.set_status(code)
            self.write(template.render(args={
                'title': 'Error...',
                'header': 'Error response',
                'body': '<p>Error code: {}</p><p>Message: {}</p>'.format(code, message),
            }))
