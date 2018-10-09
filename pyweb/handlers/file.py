import os
from .base import BaseHandler, prepare_fs, allowed_methods
from ..utils import time as time_utils
from ..utils.producers import FileProducer
from ..utils.mime import checkmime

__all__ = ['FileHandler']

class FileHandler(BaseHandler):
    @prepare_fs
    @allowed_methods()
    async def __call__(self, context, options):
        if self.fs.filetype != 'file':
            return
        filepath = self.fs.realpath
        mimetype, expire = checkmime(filepath)
        context.headers['Content-Type'] = mimetype
        if expire is not None:
            context.headers['Cache-Control'] = 'max-age=%d, must-revalidate' % expire
            if self.cache_control(context, filepath):
                return True
        if mimetype.startswith('text/'):
            return self.send_file(context, filepath)
        else:
            return self.write_bin(context, filepath, os.path.basename(filepath) if mimetype == 'application/octet-stream' else None)

    @staticmethod
    def cache_control(context, path):
        st = os.stat(path)
        context.headers['Last-Modified'] = time_utils.datetime_string(st.st_mtime)
        lm = context.env.get('HTTP_IF_MODIFIED_SINCE')
        if lm and time_utils.datetime_compare(lm, st.st_mtime):
            context.set_status(304)
            return True
        return False

    @staticmethod
    def send_file(context, path, start = None, length = None):
        if not os.path.isfile(path): return
        if length is None: length = os.path.getsize(path)
        context.headers['Content-Length'] = str(length)
        return FileProducer(path, start, length)

    @classmethod
    def write_bin(cls, context, path, filename=None):
        if filename:
            context.headers.add_header('Content-Disposition', 'attachment', filename=filename)
        context.headers['Accept-Ranges'] = 'bytes'
        fsize = os.path.getsize(path)
        if 'HTTP_RANGE' in context.env:    # protocol_version>='HTTP/1.1' and request_version>='HTTP/1.1':
            start, end = context.env['HTTP_RANGE'][6:].split('-', 1)
            try:
                start = int(start)
                end = int(end) if end else fsize - 1
                assert start <= end
                length = end - start + 1
            except:
                context.send_error(400)
            else:
                context.headers['Content-Range'] = 'bytes %d-%d/%d' % (start, end, fsize)
                if cls.cache_control(context, path): return
                context.set_status(206)
                return cls.send_file(context, path, start, length)
        else:
            return cls.send_file(context, path, length=fsize)
