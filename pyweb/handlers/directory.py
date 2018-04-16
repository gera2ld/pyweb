import os
import html
from urllib import parse
from .base import require_fs, BaseHandler
from ..utils import template

__all__ = ['DirectoryHandler']

class DirectoryHandler(BaseHandler):
    @require_fs
    async def __call__(self, context, options):
        if self.fs.filetype != 'dir':
            return
        def check_video(filename):
            base, ext = os.path.splitext(filename)
            return ext.lower() in ('.mp4', '.mkv', '.avi')
        realpath = self.fs.realpath
        try:
            assert realpath.endswith('/')
            items = sorted(os.listdir(realpath), key = str.upper)
        except:
            # not directory or not allowed to read
            return
        dir_path = self.fs.pathname.rstrip('/')
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
        data_html = ['<div class="guide">', guide, '</div>']
        data = ['<ul>']
        has_videos = False
        null = not items
        files = []
        for item in items:
            if item.startswith('.'):
                continue
            path = os.path.join(realpath, item)
            if os.path.isdir(path):
                data.append(template.render('dir-item', {
                    'href': item,
                    'name': item,
                }))
            else:
                size = os.path.getsize(path)
                for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
                    if size < 1024:
                        break
                    size = size / 1024
                if isinstance(size, float):
                    size = '%.2f' % size
                url = parse.quote(item)
                is_video = check_video(item)
                has_videos = has_videos or is_video
                files.append(''.join(template.render('file-item', {
                    'is_video': is_video,
                    'size': str(size) + unit,
                    'href': url,
                    'name': item,
                })))
        data.extend(files)
        if null:
            data.append('<li>Null</li>')
        data.append('</ul>')
        if has_videos:
            data_html.append(template.render('video'))
        data_html.extend(data)
        context.headers['Content-Type'] = 'text/html'
        return template.render(args={
            'title': 'Directory Listing',
            'header': 'Directory listing',
            'body': ''.join(data_html),
        })
