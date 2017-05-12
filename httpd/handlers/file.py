import os
from .base import BaseHandler, based_on_fs
from ..utils import FileProducer

__all__ = ['FileHandler']

class FileHandler(BaseHandler):
    @based_on_fs
    async def handle(self):
        path = self.config.find_file(self.realpath)
        if path:
            mime = self.config.get_mimetype(path)
            if mime.expire is not None:
                expire = mime.expire
            elif os.path.isfile(path):
                expire = 86400
            else:
                expire = 0
            if expire is not None:
                self.headers['Cache-Control'] = 'max-age=%d, must-revalidate' % expire
                if self.cache_control(path): return True
            self.headers['Content-Type'] = mime.name
            if mime.name.startswith('text/'):
                self.send_file(path)
            else:
                filename = os.path.basename(path)
                self.write_bin(path, filename if mime.name == 'application/octet-stream' else None)
            return True

    def cache_control(self, path):
        st = os.stat(path)
        self.headers['Last-Modified'] = self.parent.date_time_string(st.st_mtime)
        lm = self.environ.get('HTTP_IF_MODIFIED_SINCE')
        if lm and self.parent.date_time_compare(lm, st.st_mtime):
            self.set_status(304)
            return True
        return False

    def send_file(self, path, start = None, length = None):
        if not os.path.isfile(path): return
        if length is None: length = os.path.getsize(path)
        self.headers['Content-Length'] = str(length)
        self.write(FileProducer(path, start, length))

    def write_bin(self, path, filename=None):
        if filename:
            self.headers.add_header('Content-Disposition', 'attachment', filename=filename)
        self.headers['Accept-Ranges'] = 'bytes'
        fs = os.path.getsize(path)
        if 'HTTP_RANGE' in self.environ:    # self.protocol_version>='HTTP/1.1' and self.request_version>='HTTP/1.1':
            start, end = self.environ['HTTP_RANGE'][6:].split('-', 1)
            try:
                start = int(start)
                end = int(end) if end else fs - 1
                assert start <= end
                length = end - start + 1
            except:
                self.parent.send_error(400)
            else:
                self.headers['Content-Range'] = 'bytes %d-%d/%d' % (start, end, fs)
                if self.cache_control(path): return
                self.set_status(206)
                self.send_file(path, start, length)
        else:
            self.send_file(path, length = fs)
