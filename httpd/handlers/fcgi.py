import os
from ..utils import fcgi
from .base import BaseHandler, based_on_fs

__all__ = ['FCGIHandler']

class FCGIHandler(BaseHandler):
    @based_on_fs
    async def handle(self):
        fcgi_rule = self.config.get_fastcgi(self.realpath)
        if fcgi_rule:
            path = self.config.find_file(self.realpath, fcgi_rule[2])
            if path:
                await self.fcgi_handle(path, fcgi_rule)
                return True

    def fcgi_write(self, data):
        i = 0
        while not self.parent.headers_sent:
            j = data.find(b'\n', i)
            line = data[i: j].strip().decode()
            i = j + 1
            if not line:
                data = data[i:]
                break
            k, v = line.split(':', 1)
            v = v.strip()
            if k.upper() == 'STATUS':
                c, _, m = v.partition(' ')
                self.set_status(c, m)
            else:
                self.headers[k] = v
        self.write(data)

    def fcgi_err(self, data):
        if isinstance(data, bytes):
            data = data.decode('utf-8', 'replace')
        self.logger.warning(data)

    async def fcgi_handle(self, path, fcgi_rule):
        self.environ.update({
            'SCRIPT_FILENAME': os.path.abspath(path),
            'SERVER_NAME': self.parent.host or '',
            'SERVER_SOFTWARE': self.parent.server_version,
            'REDIRECT_STATUS': self.get_status()[0],
        })
        handler = fcgi.Dispatcher.get(fcgi_rule)
        try:
            await handler.run_worker(
                (self.fcgi_write, self.fcgi_err),
                self.parent.reader,
                self.environ,
            )
        except ConnectionRefusedError:
            self.parent.send_error(500, "Failed connecting to FCGI server!")
        return True
