#!python
# coding=utf-8
import sys,asyncio,locale,email.parser,http.client,urllib.parse,os,time,re
from . import fcgi, config, handlers, writers
from .log import logger
PAGE_HEADER = (
'<!DOCTYPE html>'
'<html>'
'<head>'
'<meta name=viewport content="width=device-width">'
'<meta charset=utf-8>'
'<title>%s</title>'
'<style>'
'body{font-family:Tahoma;background:#eee;color:#333;}'
'a{text-decoration:none;}'
'a:hover{text-decoration:underline;}'
'ul{margin:0;padding-left:20px;}'
'li a{display:block;word-break:break-all;}'
'li.dir{font-weight:bold;}'
'</style>'
'</head>'
'<body>'
'<h1>%s</h1>')
PAGE_FOOTER = (
'<hr>'
'%s'
'<center>&copy; 2014-2015 <a href=/>Gerald</a></center>'
'</body>'
'</html>')

class FileProducer:
    bufsize = 4096
    def __init__(self, path, start = 0, length = None):
        self.fp = open(path, 'rb')
        if start: self.fp.seek(start)
        self.length = length
    def __iter__(self):
        return self
    def __next__(self):
        if self.length is 0:
            raise StopIteration
        length = min(self.length, self.bufsize) if self.length else self.bufsize
        data = self.fp.read(length)
        if data:
            if self.length:
                self.length -= len(data)
            return data
        else:
            raise StopIteration

class HTTPHandler:
    encoding = sys.getdefaultencoding()
    sys_locale = locale.getdefaultlocale()
    server_version = 'SLHD/1.0'
    sys_version = "Python/" + sys.version.split()[0]
    protocol_version = 'HTTP/1.1'
    responses = {
        100: 'Continue',
        101: 'Switching Protocols',
        200: 'OK',
        201: 'Created',
        202: 'Accepted',
        203: 'Non-Authoritative Information',
        204: 'No Content',
        205: 'Reset Content',
        206: 'Partial Content',
        300: 'Multiple Choices',
        301: 'Moved Permanently',
        302: 'Found',
        303: 'See Other',
        304: 'Not Modified',
        305: 'Use Proxy',
        307: 'Temporary Redirect',
        400: 'Bad Request',
        401: 'Unauthorized',
        402: 'Payment Required',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        406: 'Not Acceptable',
        407: 'Proxy Authentication Required',
        408: 'Request Timeout',
        409: 'Conflict',
        410: 'Gone',
        411: 'Length Required',
        412: 'Precondition Failed',
        413: 'Request Entity Too Large',
        414: 'Request-URI Too Long',
        415: 'Unsupported Media Type',
        416: 'Requested Range Not Satisfiable',
        417: 'Expectation Failed',
        428: 'Precondition Required',
        429: 'Too Many Requests',
        431: 'Request Header Fields Too Large',
        500: 'Internal Server Error',
        501: 'Not Implemented',
        502: 'Bad Gateway',
        503: 'Service Unavailable',
        504: 'Gateway Timeout',
        505: 'HTTP Version Not Supported',
        511: 'Network Authentication Required',
    }
    handler_classes = [
        handlers.FCGIFileHandler,
    ]
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.remote_addr=writer.get_extra_info('peername')
        self.local_addr=writer.get_extra_info('sockname')
        self.config = config.get_server(port = self.local_addr[1])
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
        asyncio.async(self.handle())

    def get_path(self, path = None):
        if path is None: path = self.path
        port = self.local_addr[1]
        path, self.realpath = self.config.get_path(path)
        self.environ['DOCUMENT_URI'] = path
        path, _, query = path.partition('?')
        # TODO add PATH_INFO
        self.environ['SCRIPT_NAME'] = self.path = urllib.parse.unquote(path)
        self.environ['QUERY_STRING'] = query
        self.logger.debug('Rewrited path: %s', path)
        self.logger.debug('Real path: %s', self.realpath)

    def send_response_only(self, code, message = None):
        """Send the response header only."""
        if message is None:
            if code in self.responses:
                message = self.responses[code]
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

    GMT='%a, %d %b %Y %H:%M:%S GMT'
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
            if 'Content-Length' in self.headers:
                if self.content_encoding == 'deflate':
                    self.chunked = False
                else:
                    del self.headers['Content-Length']
        else:
            self.chunked=False
            self.close_connection = self.environ.get('HTTP_CONNECTION','close') != 'keep-alive'
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
                    if config.check_gzip(ct):
                        self.content_encoding = 'gzip'
                    break
            self.send_headers()
            writer = self.writer
            if self.chunked:
                writer = writers.ChunkedWriter(writer, self.logger)
            writer = writers.BufferedWriter(writer, self.logger)
            if self.content_encoding == 'gzip':
                writer = writers.GZipWriter(writer, self.logger)
            self.buffer = writer
        if self.command != 'HEAD':
            if isinstance(data, str):
                data = data.encode('utf-8', 'ignore')
            if isinstance(data, bytes):
                self.buffer.write(data)
            else:
                for chunk in data:
                    self.buffer.write(chunk)

    @asyncio.coroutine
    def parse_request(self):
        self.command = None  # set in case of error on the first line
        self.request_version = version = self.protocol_version
        self.close_connection = 1
        requestline = yield from asyncio.wait_for(self.reader.readline(), config.KEEP_ALIVE_TIMEOUT)
        if not requestline: return
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
            line = yield from asyncio.wait_for(self.reader.readline(),
                    config.KEEP_ALIVE_TIMEOUT)
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

    @asyncio.coroutine
    def handle(self):
        self.close_connection = 1
        while True:
            try:
                yield from self.handle_one_request()
            except (asyncio.TimeoutError, ConnectionAbortedError):
                break
            except:
                import traceback
                traceback.print_exc()
                break
            if self.close_connection: break
        self.writer.close()

    @asyncio.coroutine
    def handle_one_request(self):
        self.status = 200, 'OK'
        self.error = 0
        self.headers_sent = False
        self.headers = http.client.HTTPMessage()
        self.content_encoding = 'deflate'
        self.first_write = True
        try:
            assert (yield from self.parse_request())
        except:
            return
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
        # SCRIPT_NAME and QUERY_STRING will be set after REWRITE
        self.get_path()
        self.handlers = [handler_class(self) for handler_class in self.handler_classes]
        for handler in self.handlers:
            ret = yield from handler.handle()
            if ret: break
        self.buffer.flush()
        self.buffer.close()
        yield from self.writer.drain()
        self.logger.info('%s->%s "%s" %d %s', env['REMOTE_ADDR'], env.get('HTTP_HOST', '-'),
                self.requestline, self.status[0], '-')

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
                message = self.responses.get(code, '???')
            self.status = code,
            self.write(PAGE_HEADER % ('Error...', 'Error response'))
            self.write('<p>Error code: %d</p><p>Message: %s</p>' % (code, message))
            self.write(PAGE_FOOTER % '')

    @asyncio.coroutine
    def fcgi_write(self, data):
        i = 0
        while self.first_write:
            j = data.find(b'\n', i)
            h = data[i:j].strip().decode()
            i = j + 1
            if not h:
                data = data[i:]
                break
            k, v = h.split(':', 1)
            v = v.strip()
            if k.upper() == 'STATUS':
                c, _, m = v.partition(' ')
                self.status = int(c), m
            else:
                self.headers[k] = v
        yield from self.write(data)

    @asyncio.coroutine
    def fcgi_err(self, data):
        if isinstance(data,bytes):
            data=data.decode(self.encoding,'replace')
        self.logger.warning(data)

    @asyncio.coroutine
    def fcgi_handle(self, path, fcgi_rule):
        self.environ.update({
            'SCRIPT_FILENAME': os.path.abspath(path),
            'DOCUMENT_ROOT': self.doc_root or '',
            'SERVER_NAME': self.host or '',
            'SERVER_SOFTWARE': self.server_version,
            'REDIRECT_STATUS': self.status[0],
        })
        handler = fcgi.get_dispatcher(fcgi_rule)
        try:
            yield from handler.fcgi_run(
                self.fcgi_write, self.fcgi_err,
                self.environ,
                self.reader, self.conf.timeout
            )
        except ConnectionRefusedError:
            yield from self.send_error(500, "Failed connecting to FCGI server!")
