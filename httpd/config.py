'''
Configuration of the HTTP server.
'''
import re
import mimetypes
import os
import functools

def create_rewrite_rule(src, dest, last=False):
    if not isinstance(src, re._pattern_type):
        src = re.compile(src)
    return src, dest, last

def _rewrite_rule_group(groups):
    length = len(groups)
    def group(subs):
        key = int(subs.group(1) or subs.group(2))
        return groups[key - 1] if 0 < key <= length else ''
    return group

_pattern_sub = re.compile(r'\$(?:(\d+)|\{(\d+)\})')
def _rewrite_rule_sub(dest):
    def sub(matches):
        return _pattern_sub.sub(_rewrite_rule_group(matches.groups()), dest)
    return sub

def _rewrite_rule_apply(rule, path):
    src, dest, last = rule
    path, count = src.subn(_rewrite_rule_sub(dest), path)
    return path if count > 0 else None, last

def apply_rewrite_rules(rules, path):
    for rule in rules:
        path_, last = _rewrite_rule_apply(rule, path)
        if path_ is not None:
            path = path_
            if last:
                break
    return path

def create_alias_rule(src, dest):
    if not src: src = './'
    if not dest: dest = './'
    if src.endswith('/') is not dest.endswith('/'):
        if not src.endswith('/'): src += '/'
        if not dest.endswith('/'): dest += '/'
    dest = os.path.expanduser(dest)
    return src, dest, len(src)

def apply_alias_rules(rules, path):
    for rule in rules:
        src, dest, len_src = rule
        pre, suf = path[:len_src], path[len_src:]
        if (pre.endswith('/') or suf.startswith('/')) and pre == src:
            return dest + suf, dest
    return '.' + path, './'

def create_fcgi_rule(src, addrs, indexes, timeout=10):
    if not isinstance(src, re._pattern_type):
        src = re.compile(src)
    for addr in addrs:
        host, port = addr
        assert isinstance(host, str) and isinstance(port, int), 'Invalid address'
    return src, addrs, indexes, timeout

def apply_fcgi_rules(rules, path):
    for rule in rules:
        src = rule[0]
        if src.search(path):
            return rule

class ServerConfig:
    keep_alive_timeout = 120

    def __init__(self, parent=None, host='', port=80):
        if parent is None:
            parent = Config()
        self.parent = parent
        self.host = host
        self.port = port
        self.rewrites = []
        self.aliases = []
        self.indexes = ['index.html']
        self.fcgi = []

    def add_rewrite(self, src, dest, last=False):
        self.rewrites.append(create_rewrite_rule(src, dest, last))

    def add_alias(self, src, dest):
        self.aliases.append(create_alias_rule(src, dest))

    def add_fastcgi(self, src, addr, indexes=None):
        self.fcgi.append(create_fcgi_rule(src, addr, indexes))

    def set_indexes(self, indexes):
        self.indexes = list(indexes)

    def get_path(self, path):
        path = apply_rewrite_rules(self.rewrites, path)
        realpath, doc_root = apply_alias_rules(self.aliases, path)
        realpath = realpath.split('?', 1)[0]
        return path, realpath, doc_root

    def find_file(self, realpath, indexes=None):
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
        return apply_fcgi_rules(self.fcgi, path)

    def check_gzip(self, *k, **kw):
        return self.parent.check_gzip(*k, **kw)

    def get_mimetype(self, *k, **kw):
        return self.parent.get_mimetype(*k, **kw)

class Config:
    def __init__(self):
        self.servers = {}
        self.mimetypes = {}
        self.gzip_types = set()

    # TODO add subdomain support
    def get_server(self, host='', port=80):
        servers = self.servers.get(port, {})
        server = servers.get(host)
        if server is None and host:
            server = servers.get('')
        return server

    def add_server(self, host='', port=80):
        port = int(port)
        servers = self.servers.setdefault(port, {})
        server = servers.get(host)
        if server is not None:
            logger.warn(
                'Server %s:%d already exists and will be replaced by the latest one.', host, port)
        server = servers[host] = ServerConfig(self, host, port)
        return server

    def add_gzip(self, mimetypes):
        if isinstance(mimetypes, str):
            mimetypes = [mimetypes]
        self.gzip_types.update(mimetypes)

    def check_gzip(self, mimetype):
        return mimetype in self.gzip_types

    def add_mimetype(self, exts, name, expire=None):
        mimetype = MimeType(name, expire)
        if not isinstance(exts, list):
            exts = [exts]
        for ext in exts:
            self.mimetypes[ext] = mimetype

    def get_mimetype(self, path=None, ext=None):
        if path is not None:
            _, ext = os.path.splitext(path)
        return MimeType.get(ext, self.mimetypes)

class MimeType:
    expire = 0
    types = None

    def __init__(self, name, expire=None):
        self.name = name
        if expire is not None:
            self.expire = expire

    @classmethod
    def initialize(cls):
        if not mimetypes.inited:
            mimetypes.init()
        cls.types = {
            None: MimeType('application/octet-stream', 0),
        }
        for ext, mime in mimetypes.types_map.items():
            cls.types[ext] = cls(mime)

    @classmethod
    def get(cls, ext, types=None):
        if cls.types is None: cls.initialize()
        ext = ext.lower()
        if types is not None:
            mimetype = types.get(ext)
        if mimetype is None:
            mimetype = cls.types.get(ext) or cls.types[None]
        return mimetype
