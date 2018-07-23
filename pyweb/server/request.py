import email.parser
import http.client
import asyncio
from ..utils import errors

class Request:
    def __init__(self, reader, protocol_version,
            keep_alive_timeout=120, env=()):
        self.reader = reader
        self.protocol_version = protocol_version
        self.keep_alive = False
        self.keep_alive_timeout = keep_alive_timeout
        self.requestline = None
        self.method = None
        self.path = None
        self.hostname = None
        self.port = None
        self.headers = None
        self.env = env
        self._accept = None

    async def parse(self):
        requestline = await asyncio.wait_for(self.reader.readline(), self.keep_alive_timeout)
        if not requestline:
            return
        self.requestline = requestline.strip().decode()
        if not self.requestline:
            return
        words = self.requestline.split(' ')
        assert len(words) == 3, 'Bad request syntax (%r)' % self.requestline
        self.method, self.path, version = words
        assert version.startswith('HTTP/'), 'Bad request version (%r)' % version
        version_number = version[5:].split('.')
        assert len(version_number) == 2, 'Bad request version (%r)' % version
        protocol_version = tuple(map(int, version_number))
        if protocol_version >= (2, 0):
            raise errors.HTTPError(505, "Invalid HTTP Version (%s)" % version)
        if protocol_version >= (1, 1):
            self.keep_alive = True
        if protocol_version < self.protocol_version:
            self.protocol_version = protocol_version
        # Examine the headers and look for a Connection directive.
        header_lines = []
        while True:
            line = await asyncio.wait_for(self.reader.readline(), self.keep_alive_timeout)
            if not line.strip():
                break
            header_lines.append(line.decode())
        try:
            parser = email.parser.Parser(_class=http.client.HTTPMessage)
            self.headers = parser.parsestr(''.join(header_lines))
        except http.client.LineTooLong:
            raise errors.HTTPError(400, "Line too long")
        conntype = self.headers.get('Connection', "")
        if conntype.lower() == 'close':
            self.keep_alive = False
        elif conntype.lower() == 'keep-alive' and protocol_version >= (1, 1):
            self.keep_alive = True
        self.env['SERVER_PROTOCOL'] = 'HTTP/%d.%d' % protocol_version
        self.env['REQUEST_METHOD'] = self.method
        self.env['CONTENT_TYPE'] = self.headers.get('content-type')
        self.env['CONTENT_LENGTH'] = self.headers.get('content-length')
        for key, value in self.headers.items():
            key = key.replace('-', '_').upper()
            if key in self.env:
                continue
            key = 'HTTP_' + key
            value = value.strip()
            oldvalue = self.env.get(key)
            if oldvalue is None:
                self.env[key] = value
            else:
                self.env[key] = oldvalue + ',' + value
        self.env['REQUEST_URI'] = self.path
        host = self.env.get('HTTP_HOST')
        self.port = None
        if host:
            hostname, _, port = host.rpartition(':')
            if _:
                self.hostname = hostname
                self.port = int(port)
        self._accept = self.init_q(self.headers.get('accept'))
        self._accept_encoding = self.init_q(self.headers.get('accept-encoding'))
        return True

    def init_q(self, raw):
        data = {}
        if raw:
            for item in raw.split(','):
                key, _, q = item.strip().partition(';q=')
                try:
                    q = float(q)
                except:
                    q = 1.0
                data[key] = q
        return data

    def accept(self, key):
        q = self._accept.get(key)
        return q is not None and q > 0

    def accept_encoding(self, key):
        q = self._accept_encoding.get(key)
        return q is not None and q > 0
