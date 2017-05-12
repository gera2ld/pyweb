import functools
from urllib import parse

def based_on_fs(handle):
    @functools.wraps(handle)
    async def wrapped_handle(self):
        parent = self.parent
        port = parent.local_addr[1]
        path, realpath, doc_root = self.config.get_path(parent.path)
        self.environ['DOCUMENT_ROOT'] = doc_root
        self.environ['DOCUMENT_URI'] = path
        path, _, query = path.partition('?')
        self.environ['SCRIPT_NAME'] = self.path = parse.unquote(path)
        self.environ['QUERY_STRING'] = query
        self.realpath = parse.unquote(realpath)
        parent.logger.debug('Rewrited path: %s', path)
        parent.logger.debug('Real path: %s', self.realpath)
        return await handle(self)
    return wrapped_handle

class BaseHandler:
    def __init__(self, parent):
        self.parent = parent
        self.config = parent.config
        self.headers = parent.headers
        self.environ = parent.environ
        self.write = parent.write
        self.logger = parent.logger

    def get_status(self):
        return self.parent.status

    def set_status(self, code, message = None):
        self.parent.status = int(code), message

    async def handle(self):
        '''
        MUST be overridden
        '''
        raise NotImplementedError
