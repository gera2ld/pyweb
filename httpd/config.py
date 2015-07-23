#!/usr/bin/env python
# coding=utf-8
import re, mimetypes, os
KEEP_ALIVE_TIMEOUT = 120

class RewriteRule:
    def __init__(self, src, dest, last = False):
        if not isinstance(src, re._pattern_type):
            src = re.compile(src)
        self.src = src
        self.dest = dest
        self.last = last

    _pattern_sub = re.compile(r'\$(?:(\d+)|\{(\d+)\})')
    def _replace(self, matches):
        def get_sub(subs):
            key = int(m.group(1) or m.group(2))
            return matches[key - 1] if 0 < key <= length else ''
        groups = matches.groups()
        length = len(groups)
        return self._pattern_sub.sub(get_sub, self.dest)

    def apply(self, path):
        path, count = self.src.subn(self._replace, path)
        if count > 0:
            return path

class AliasRule:
    def __init__(self, src, dest):
        assert src.endswith('/') is dest.endswith('/'), 'Source and destination must be both files or directories.'
        self.src = src
        self.dest = os.path.expanduser(dest)
        self.len_src = len(src)

    def apply(self, path):
        parts = path[:self.len_src], path[self.len_src:]
        if (parts[0].endswith('/') or parts[1].startswith('/')) and parts[0] == self.src:
            return self.dest + parts[1]

class FastCGIRule:
    timeout = 10
    def __init__(self, src, addr, indexes, timeout = None):
        if not isinstance(src, re._pattern_type):
            src = re.compile(src)
        self.src = src
        if not isinstance(addr, list):
            addr = [addr]
        self.addr = addr
        self.indexes = indexes
        if timeout:
            self.timeout = timeout

    def apply(self, path):
        if self.src.search(path):
            return self

class ServerConfig:
    fallback_alias = AliasRule('/', './')

    def __init__(self, host = '', port = 80):
        self.host = host
        self.port = port
        self.rewrites = []
        self.aliases = []
        self.indexes = ['index.html']
        self.fcgi = []

    def add_rewrite(self, src, dest, last = False):
        self.rewrites.append(RewriteRule(src, dest, last))

    def add_alias(self, src, dest):
        self.aliases.append(AliasRule(src, dest))

    def add_fastcgi(self, src, addr, indexes = None):
        self.fcgi.append(FastCGIRule(src, addr, indexes))

    def set_indexes(self, indexes):
        self.indexes = list(indexes)

    def get_path(self, path):
        for rewrite in self.rewrites:
            _path = rewrite.apply(path)
            if _path:
                path = _path
                if rewrite.last: break
        for alias in self.aliases:
            realpath = alias.apply(path)
            if realpath:
                doc_root = alias.dest
                break
        else:
            realpath = self.fallback_alias.apply(path)
            doc_root = self.fallback_alias.dest
        return path, realpath, doc_root

    def find_file(self, realpath, indexes = None):
        if os.path.isfile(realpath):
            return realpath
        if realpath.endswith('/') and os.path.isdir(realpath):
            if indexes is None:
                # in case indexes is []
                indexes = self.indexes
            for i in indexes:
                path = os.path.join(realpath, i)
                if os.path.isfile(path):
                    return path

    def get_fastcgi(self, path):
        for rule in self.fcgi:
            rule = rule.apply(path)
            if rule: return rule

class Config:
    def __init__(self):
        self.servers = {}
        self.gzip_types = set()

    # TODO add subdomain support
    def get_server(self, host = '', port = 80):
        servers = self.servers.get(port, {})
        server = servers.get(host)
        if server is None and host:
            server = servers.get('')
        return server

    def add_server(self, host = '', port = 80, exist_ok = True):
        servers = self.servers.setdefault(port, {})
        server = servers.get(host)
        if not exist_ok:
            assert server is None, 'Server %s:%d already exists.' % (host, port)
        if server is None:
            server = servers[host] = ServerConfig(host, port)
        return server

    def add_gzip(self, mimetypes):
        if isinstance(mimetypes, str):
            mimetypes = [mimetypes]
        self.gzip_types.update(mimetypes)

    def check_gzip(self, mimetype):
        return mimetype in self.gzip_types

config = Config()
get_server = config.get_server
add_server = config.add_server
add_gzip = config.add_gzip
check_gzip = config.check_gzip
servers = config.servers

class MimeType:
    expire = 3600
    def __init__(self, name, expire = None):
        self.name = name
        if expire is not None:
            self.expire = expire

_mimetypes = {}
def init_mimetypes():
    if not mimetypes.inited:
        mimetypes.init()
    for ext, mime in mimetypes.types_map.items():
        _mimetypes[ext] = MimeType(mime)

def get_mime(path):
    _, ext = os.path.splitext(path)
    return _mimetypes.get(ext)

init_mimetypes()
