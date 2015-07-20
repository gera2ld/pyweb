#!/usr/bin/env python
# coding=utf-8
import asyncio
from . import config

class BaseHandler:
    def __init__(self, parent):
        self.parent = parent
        self.config = parent.config
        self.headers = parent.headers
        self.write = parent.write
        self.logger = parent.logger

    @asyncio.coroutine
    def handle(self, realpath = None):
        '''
        Should be overridden
        '''
        self.parent.send_error(404)
        return True

class FileHandler(BaseHandler):
    subhandlers = ['handle_file']
    @asyncio.coroutine
    def handle(self, realpath = None):
        path = self.config.find_file(realpath or self.parent.realpath)
        if path is None:
            self.parent.send_error(404)
            return True
        for subhandle in self.subhandlers:
            handle = getattr(self, subhandle, None)
            if handle and (yield from handle(path)):
                return True

    def cache_control(self, path):
        st = os.stat(path)
        self.headers['Last-Modified'] = self.date_time_string(st.st_mtime)
        lm = self.environ.get('HTTP_IF_MODIFIED_SINCE')
        if lm and self.date_time_compare(lm, st.st_mtime):
            self.status = 304,
            return True
        return False

    @asyncio.coroutine
    def handle_file(self, path):
        self.logger.debug('File handler')
        mime = config.get_mime(path)
        if mime:
            if mime.expire:
                expire = mime.expire
            elif os.path.isfile(path):
                expire = 86400
            else:
                expire = 0
            if expire:
                self.headers['Cache-Control'] = 'max-age=%d, must-revalidate' % expire
                if self.cache_control(path): return
            self.headers['Content-Type'] = mime.name
            self.send_file(path)
        else:
            self.write_bin(path)
        return True

    def send_file(self, path, start = None, length = None):
        if not os.path.isfile(path): return
        if length is None: length = os.path.getsize(path)
        self.headers['Content-Length'] = str(length)
        self.write(FileProducer(path, start, length))

    def write_bin(self, path):
        self.headers['Content-Type'] = 'application/octet-stream'
        self.headers.add_header('Content-Disposition', 'attachment', filename = os.path.basename(path))
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
                self.send_error(400)
            else:
                self.headers['Content-Range'] = 'bytes %d-%d/%d' % (start, end, fs)
                if self.cache_control(path): return
                self.status = 206,
                self.send_file(path, start, length)
        else:
            self.send_file(path, length = fs)

class FCGIFileHandler(FileHandler):
    subhandlers = ['handle_fcgi', 'handle_file']

    @asyncio.coroutine
    def handle_fcgi(self, path):
        self.logger.debug('FCGI handler')
        fcgi_rule = self.config.get_fastcgi(path)
        if fcgi_rule:
            yield from self.fcgi_handle(path, fcgi_rule)
            return True
