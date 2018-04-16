import os
from ..utils import fcgi
from .base import BaseHandler, require_fs

__all__ = ['FCGIHandler']

class FCGIHandler(BaseHandler):
    @require_fs
    async def __call__(self, context, options):
        if self.fs.filetype != 'file':
            return
        filepath = self.fs.realpath
        _, extname = os.path.splitext(filepath)
        extnames = options.get('fcgi_ext')
        target = options.get('fcgi_target')
        if not target or not extnames or extname not in extnames:
            return

        def _fcgi_write(data):
            i = 0
            while not context.headers_sent:
                j = data.find(b'\n', i)
                line = data[i: j].strip().decode()
                i = j + 1
                if not line:
                    data = data[i:]
                    break
                key, value = line.split(':', 1)
                value = value.strip()
                if key.upper() == 'STATUS':
                    code, _, msg = value.partition(' ')
                    context.set_status(code, msg)
                else:
                    context.headers[key] = value
            context.write(data)

        def _fcgi_err(data):
            if isinstance(data, bytes):
                data = data.decode('utf-8', 'replace')
            context.logger.warning(data)

        context.env.update({
            'SCRIPT_FILENAME': os.path.abspath(filepath),
            'SERVER_NAME': context.request.hostname or '',
            'SERVER_SOFTWARE': context.server_version,
            'REDIRECT_STATUS': context.status[0],
        })
        handler = fcgi.Dispatcher.get(target)
        try:
            await handler.run_worker(_fcgi_write, _fcgi_err, context.reader, context.env)
        except ConnectionRefusedError:
            context.send_error(500, "Failed connecting to FCGI server!")

        return True
