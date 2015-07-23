#!/usr/bin/env python
# coding=utf-8
import asyncio, os, html
from urllib import parse
from . import config, template, fcgi

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

class BaseHandler:
    def __init__(self, parent):
        self.parent = parent
        self.config = parent.config
        self.headers = parent.headers
        self.environ = parent.environ
        self.write = parent.write
        self.logger = parent.logger

    @asyncio.coroutine
    def handle(self, realpath):
        '''
        Should be overridden
        '''
        self.parent.send_error(404)
        return True

class FCGIHandler(BaseHandler):
    @asyncio.coroutine
    def handle(self, realpath):
        fcgi_rule = self.config.get_fastcgi(realpath)
        if fcgi_rule:
            path = self.config.find_file(realpath, fcgi_rule.indexes)
            if path:
                yield from self.fcgi_handle(path, fcgi_rule)
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
                self.parent.status = int(c), m
            else:
                self.headers[k] = v
        self.write(data)

    def fcgi_err(self, data):
        if isinstance(data, bytes):
            data = data.decode('utf-8', 'replace')
        self.logger.warning(data)

    @asyncio.coroutine
    def fcgi_handle(self, path, fcgi_rule):
        self.environ.update({
            'SCRIPT_FILENAME': os.path.abspath(path),
            'DOCUMENT_ROOT': self.parent.doc_root or '',
            'SERVER_NAME': self.parent.host or '',
            'SERVER_SOFTWARE': self.parent.server_version,
            'REDIRECT_STATUS': self.parent.status[0],
        })
        handler = fcgi.get_dispatcher(fcgi_rule)
        try:
            yield from handler.fcgi_run(
                self.fcgi_write, self.fcgi_err,
                self.environ,
                self.parent.reader, fcgi_rule.timeout
            )
        except ConnectionRefusedError:
            yield from self.parent.send_error(500, "Failed connecting to FCGI server!")
        return True

class FileHandler(BaseHandler):
    @asyncio.coroutine
    def handle(self, realpath):
        path = self.config.find_file(realpath)
        if path:
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

    def cache_control(self, path):
        st = os.stat(path)
        self.headers['Last-Modified'] = self.parent.date_time_string(st.st_mtime)
        lm = self.environ.get('HTTP_IF_MODIFIED_SINCE')
        if lm and self.date_time_compare(lm, st.st_mtime):
            self.status = 304,
            return True
        return False

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
                self.parent.send_error(400)
            else:
                self.headers['Content-Range'] = 'bytes %d-%d/%d' % (start, end, fs)
                if self.cache_control(path): return
                self.status = 206,
                self.send_file(path, start, length)
        else:
            self.send_file(path, length = fs)

class DirectoryHandler(BaseHandler):
    @asyncio.coroutine
    def handle(self, realpath):
        try:
            assert realpath.endswith('/')
            items = sorted(os.listdir(realpath), key = str.upper)
        except:
            # not directory or not allowed to read
            return
        dir_path = self.parent.path.rstrip('/')
        parts = dir_path.split('/')
        pre = ''
        dirs = []
        for part in reversed(parts):
            part = part or 'Home'
            if pre:
                part = '<a href="%s">%s</a>' % (pre, part)
            pre += '../'
            dirs.append(part)
        guide = ' / '.join(reversed(dirs))
        data = [guide, '<hr><ul>']
        null = not items
        files = []
        for item in items:
            if item.startswith('.'):
                continue
            path = os.path.join(realpath, item)
            if os.path.isdir(path):
                data.append(
                    '<li class="dir">'
                        '<a href="%s/">'
                            '<span class="type">[DIR]</span> %s'
                        '</a>'
                    '</li>' % (parse.quote(item), html.escape(item))
                )
            else:
                size = os.path.getsize(path)
                for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
                    if size < 1024: break
                    size = size / 1024
                if isinstance(size, float):
                    size = '%.2f' % size
                files.append(
                    '<li class="file">'
                        '<a href="%s">'
                            '<span class="type">[%s%s]</span> %s'
                        '</a>'
                    '</li>' % (parse.quote(item), size, unit, html.escape(item))
                )
        data.extend(files)
        if null:
            data.append('<li>Null</li>')
        data.append('</ul>')
        self.write(template.render(
            title = 'Directory Listing',
            head = (
                '<style>'
                    'ul{margin:0;padding-left:20px;}'
                    'li a{display:block;word-break:break-all;}'
                    'li.dir{font-weight:bold;}'
                '</style>'
            ),
            header = 'Directory listing for ' + (dir_path or '/'),
            body = ''.join(data)
        ))
        return True

class NotFoundHandler(BaseHandler):
    pass
