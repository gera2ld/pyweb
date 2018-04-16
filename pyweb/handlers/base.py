import os
import functools
from urllib import parse

def check_filetype(filepath):
    if os.path.isdir(filepath):
        return 'dir'
    elif os.path.isfile(filepath):
        return 'file'

class FileSystemInfo:
    def __init__(self, context, options):
        root = options.get('root', '.')
        path = context.request.path
        pathname, _, query = path.partition('?')
        pathname = parse.unquote(pathname)
        self.pathname = pathname
        context.env.update({
            'DOCUMENT_ROOT': root,
            'DOCUMENT_URI': path,
            'SCRIPT_NAME': pathname,
            'QUERY_STRING': query,
        })
        if pathname.startswith('/~/'):
            filepath = os.path.join(os.path.dirname(__file__), '../static', pathname[3:])
        else:
            filepath = os.path.join(root, pathname[1:])
        if os.name == 'nt':
            filepath = filepath.replace('\\', '/')
        filetype = check_filetype(filepath)
        self.filetype = filetype
        self.realpath = None if filetype is None else filepath

        # Check index files
        index = options.get('index')
        if filetype == 'dir' and index:
            for item in index:
                indexpath = os.path.join(filepath, item)
                indextype = check_filetype(indexpath)
                if indextype == 'file':
                    self.realpath = indexpath
                    self.filetype = indextype
                    break

    def __repr__(self):
        return f'<FileSystemInfo type={self.filetype} path={self.pathname} realpath={self.realpath}>'

def require_fs(handle):
    @functools.wraps(handle)
    async def wrapped_handle(self, context, options):
        self.fs = FileSystemInfo(context, options)
        return await handle(self, context, options)
    return wrapped_handle

class BaseHandler:
    fs = None

    def __repr__(self):
        return '<{}>'.format(self.__class__.__name__)
