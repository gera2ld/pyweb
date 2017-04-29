import sys, asyncio, email.parser, http.client, http.server, time
from . import handlers, writers, template, __version__
from .log import logger

class HTTPHandler:
    server_version = 'SLHD/' + __version__
    sys_version = "Python/" + sys.version.split()[0]
    protocol_version = 'HTTP/1.1'
    # responses is a dict of {status_code: (short_reason, empty_str_or_long_reason)}
    responses = http.server.BaseHTTPRequestHandler.responses.copy()
    handler_classes = [
        handlers.FCGIHandler,
        handlers.FileHandler,
        handlers.DirectoryHandler,
        handlers.NotFoundHandler,
    ]
    def __init__(self, reader, writer, config):
        self.reader = reader
        self.writer = writer
        self.remote_addr = writer.get_extra_info('peername')
        self.local_addr = writer.get_extra_info('sockname')
        self.config = config
        self.logger = logger.getChild(str(self.config.port))
        #self.logger.setLevel(self.conf.get('loglevel')*10)
        env = self.base_environ = {}
        env['GATEWAY_INTERFACE'] = 'CGI/1.1'
        env['SERVER_ADDR'] = self.local_addr[0]
        env['SERVER_PORT'] = str(self.local_addr[1])
        env['REMOTE_ADDR'] = self.remote_addr[0]
        env['REMOTE_PORT'] = str(self.remote_addr[1])
        env['CONTENT_LENGTH'] = ''
        env['SCRIPT_NAME'] = ''

    def send_response_only(self, code, message = None):
        """Send the response header only."""
        if message is None:
            if code in self.responses:
                message = self.responses[code][0]
            else:
                message = ''
        if self.request_version != 'HTTP/0.9':
            if not hasattr(self, '_headers_buffer'):
                self._headers_buffer = []
            self._headers_buffer.append(("%s %d %s\r\n" %
                    (self.protocol_version, code, message)).encode(
                        'latin-1', 'strict'))

    def send_header(self, keyword, value):
        """Send a MIME header to the headers buffer."""
        if self.request_version != 'HTTP/0.9':
            if not hasattr(self, '_headers_buffer'):
                self._headers_buffer = []
            self._headers_buffer.append(
                ("%s: %s\r\n" % (keyword, value)).encode('latin-1', 'strict'))

        if keyword.lower() == 'connection':
            if value.lower() == 'close':
                self.close_connection = 1
            elif value.lower() == 'keep-alive':
                self.close_connection = 0

    def end_headers(self):
        """Send the blank line ending the MIME headers."""
        if self.request_version != 'HTTP/0.9':
            self._headers_buffer.append(b"\r\n")
            self.flush_headers()

    def flush_headers(self):
        if hasattr(self, '_headers_buffer'):
            self.writer.writelines(self._headers_buffer)
            self._headers_buffer = []

    def version_string(self):
        """Return the server software version string."""
        return self.server_version + ' ' + self.sys_version

    GMT = '%a, %d %b %Y %H:%M:%S GMT'
    def date_time_string(self, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        return time.strftime(self.GMT, time.localtime(timestamp))

    def date_time_compare(self, t1, t2):
        if isinstance(t1, str):
            t1 = time.mktime(time.strptime(t1, self.GMT))
        if isinstance(t2, str):
            t2 = time.mktime(time.strptime(t2, self.GMT))
        return t1 >= t2

    def send_headers(self):
        if self.protocol_version >= 'HTTP/1.1' and self.request_version >= 'HTTP/1.1':
            self.close_connection = self.environ.get('HTTP_CONNECTION', 'keep-alive') != 'keep-alive'
            self.chunked = True # only allowed in HTTP/1.1
            if self.status[0] in (204, 304):
                self.chunked = False
            elif 'Content-Length' in self.headers:
                if self.content_encoding == 'deflate':
                    self.chunked = False
                else:
                    del self.headers['Content-Length']
        else:
            self.chunked = False
            self.close_connection = self.environ.get('HTTP_CONNECTION', 'close') != 'keep-alive'
        if self.content_encoding == 'gzip':
            self.headers['Content-Encoding'] = 'gzip'
        if self.chunked:
            self.headers['Transfer-Encoding'] = 'chunked'
        else:
            self.close_connection = 1
        self.headers['Connection'] = 'close' if self.close_connection else 'keep-alive'
        self.headers.add_header('Server', self.version_string())
        self.headers.add_header('Date', self.date_time_string())
        # send headers
        self.send_response_only(*self.status)
        for k, v in self.headers.items(): self.send_header(k, v)
        self.end_headers()
        self.headers_sent = True

    def write(self, data):
        if not self.headers_sent:
            for i in map(lambda x: x.split(';', 1), self.environ.get('HTTP_ACCEPT_ENCODING', '').split(',')):
                if i[0] == 'gzip':
                    ct = self.headers.get('Content-Type', '')
                    if self.config.check_gzip(ct):
                        self.content_encoding = 'gzip'
                    break
            self.send_headers()
            writer = self.raw_writer = writers.RawWriter(self.writer, self.logger)
            if self.chunked:
                writer = writers.ChunkedWriter(writer, self.logger)
            writer = writers.BufferedWriter(writer, self.logger)
            if self.content_encoding == 'gzip':
                writer = writers.GZipWriter(writer, self.logger)
            self.buffer = writer
        if self.command != 'HEAD' and data:
            if isinstance(data, str):
                data = data.encode('utf-8', 'ignore')
            if self.chunked_data is not None:
                self.chunked_data.append(data)
            elif isinstance(data, bytes):
                self.buffer.write(data)
            else:
                self.chunked_data = [data]

    async def parse_request(self):
        self.command = None  # set in case of error on the first line
        self.request_version = version = self.protocol_version
        self.close_connection = 1
        requestline = await asyncio.wait_for(self.reader.readline(), self.config.keep_alive_timeout)
        if not requestline: return False
        self.requestline = requestline.strip().decode()
        words = self.requestline.split()
        if len(words) == 3:
            command, path, version = words
            if version[:5] != 'HTTP/':
                self.send_error(400, "Bad request version (%r)" % version)
                return
            try:
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except (ValueError, IndexError):
                self.send_error(400, "Bad request version (%r)" % version)
                return
            if version_number >= (1, 1) and self.protocol_version >= "HTTP/1.1":
                self.close_connection = 0
            if version_number >= (2, 0):
                self.send_error(505, "Invalid HTTP Version (%s)" % base_version_number)
                return
        else:
            if words:
                self.send_error(400, "Bad request syntax (%r)" % self.requestline)
            return

        self.command, self.path, self.request_version = command, path, version
        # Examine the headers and look for a Connection directive.
        headers = []
        while True:
            line = await asyncio.wait_for(self.reader.readline(), self.config.keep_alive_timeout)
            if not line.strip(): break
            headers.append(line.decode())
        try:
            self.req_headers = email.parser.Parser(
                    _class = http.client.HTTPMessage).parsestr(''.join(headers))
        except http.client.LineTooLong:
            self.send_error(400, "Line too long")
            return

        conntype = self.req_headers.get('Connection', "")
        if conntype.lower() == 'close':
            self.close_connection = 1
        elif conntype.lower() == 'keep-alive' and self.protocol_version >= "HTTP/1.1":
            self.close_connection = 0
        return True

    async def handle(self):
        self.close_connection = 1
        self.clean()
        while True:
            try:
                await self.handle_one_request()
            except (asyncio.TimeoutError, ConnectionError):
                break
            except:
                import traceback
                traceback.print_exc()
                break
            finally:
                self.clean()
                env = getattr(self, 'environ', None)
                if env:
                    written = self.raw_writer.written if self.raw_writer else '-'
                    self.logger.info('%s->%s "%s" %d %s',
                        env['REMOTE_ADDR'], env.get('HTTP_HOST', '-'),
                        self.requestline, self.status[0], written)
            if self.close_connection: break
        self.writer.close()

    def get_environ(self):
        env = self.environ = self.base_environ.copy()
        env['SERVER_PROTOCOL'] = self.request_version
        env['REQUEST_METHOD'] = self.command
        env['CONTENT_TYPE'] = self.req_headers.get('Content-Type')
        env['CONTENT_LENGTH'] = self.req_headers.get('Content-Length')
        for k, v in self.req_headers.items():
            k = k.replace('-', '_').upper()
            if k in env: continue
            k = 'HTTP_' + k
            v = v.strip()
            if k in env:
                env[k] += ','+v  # comma-separate multiple headers
            else:
                env[k] = v
        env['REQUEST_URI'] = self.path
        self.host = env.get('HTTP_HOST')
        self.port = 80
        if self.host:
            host, _, port = self.host.rpartition(':')
            if _:
                self.host = host
                self.port = int(port)

    def clean(self):
        chunked_data = getattr(self, 'chunked_data', None)
        if chunked_data is not None:
            for gen in chunked_data:
                if hasattr(gen, 'close'):
                    gen.close()
        self.status = 200, 'OK'
        self.error = 0
        self.headers_sent = False
        self.headers = None
        self.content_encoding = 'deflate'
        self.chunked_data = None
        self.raw_writer = None
        self.realpath = None

    async def handle_one_request(self):
        self.headers = http.client.HTTPMessage()
        try:
            res = await self.parse_request()
            # res is False when connection is lost
            assert res is not False
        except:
            return
        self.get_environ()
        # res is None for bad requests
        if not res: return
        self.handlers = [handler_class(self) for handler_class in self.handler_classes]
        for handler in self.handlers:
            ret = await handler.handle()
            if ret: break
        if self.chunked_data:
            for gen in self.chunked_data:
                for chunk in gen:
                    if self.writer.transport._conn_lost:
                        return
                    self.buffer.write(chunk)
                    await self.writer.drain()
        else:
            self.write(None)
        self.buffer.flush()
        self.buffer.close()
        await self.writer.drain()

    def redirect(self, url, code = 303, message = None):
        self.status = code,
        self.headers['Location'] = url
        if message is None:
            message = 'The URL has been moved <a href="%s">here</a>.' % url
        self.write(message)

    def send_error(self, code, message = None):
        if code >= 200 and code not in (204, 304):
            self.headers['Content-Type'] = 'text/html'
            if message is None:
                _, message = self.responses.get(code, (None, '???'))
            self.status = code,
            self.write(template.render(
                title = 'Error...',
                header = 'Error response',
                body = '<p>Error code: %d</p><p>Message: %s</p>' % (code, message)
            ))
