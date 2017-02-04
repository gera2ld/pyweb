import re, mimetypes, os

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
            key = int(subs.group(1) or subs.group(2))
            return groups[key - 1] if 0 < key <= length else ''
        groups = matches.groups()
        length = len(groups)
        return self._pattern_sub.sub(get_sub, self.dest)

    def apply(self, path):
        path, count = self.src.subn(self._replace, path)
        if count > 0:
            return path

class AliasRule:
    def __init__(self, src, dest):
        if not src: src = './'
        if not dest: dest = './'
        if src.endswith('/') is not dest.endswith('/'):
            if not src.endswith('/'): src += '/'
            if not dest.endswith('/'): dest += '/'
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
    keep_alive_timeout = 120
    fallback_alias = AliasRule('/', './')

    def __init__(self, parent=None, host = '', port = 80):
        if parent is None:
            parent = Config()
        self.parent = parent
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
        realpath = realpath.split('?', 1)[0]
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
    def get_server(self, host = '', port = 80):
        servers = self.servers.get(port, {})
        server = servers.get(host)
        if server is None and host:
            server = servers.get('')
        return server

    def add_server(self, host = '', port = 80, exist_ok = True):
        port = int(port)
        servers = self.servers.setdefault(port, {})
        server = servers.get(host)
        if not exist_ok:
            assert server is None, 'Server %s:%d already exists.' % (host, port)
        if server is None:
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

    def __init__(self, name, expire = None):
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
