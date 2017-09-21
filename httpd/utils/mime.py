import os
import mimetypes

if not mimetypes.inited:
    mimetypes.init()

mimetypes.add_type('.js', 'application/javascript')

expires = {
    # 'application/javascript': 86400,
    # 'text/css': 86400,
    # 'text/html': 86400,
}

def checkmime(filepath):
    mimetype, _enc = mimetypes.guess_type(filepath)
    if mimetype is None:
        mimetype = 'application/octet-stream'
    expire = expires.get(mimetype)
    if expire is None:
        _basename, extname = os.path.splitext(filepath)
        expire = expires.get(extname, 0)
    return mimetype, expire
