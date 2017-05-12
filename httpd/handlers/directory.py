import os
import html
from urllib import parse
from .base import BaseHandler, based_on_fs
from .. import template

__all__ = ['DirectoryHandler']

class DirectoryHandler(BaseHandler):
    @based_on_fs
    async def handle(self):
        def is_video(filename):
            base, ext = os.path.splitext(filename)
            return ext.lower() in ('.mp4', '.mkv', '.avi')
        try:
            assert self.realpath.endswith('/')
            items = sorted(os.listdir(self.realpath), key = str.upper)
        except:
            # not directory or not allowed to read
            return
        dir_path = self.path.rstrip('/')
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
        dataHtml = [guide]
        data = ['<hr><ul>']
        hasVideos = False
        null = not items
        files = []
        for item in items:
            if item.startswith('.'):
                continue
            path = os.path.join(self.realpath, item)
            if os.path.isdir(path):
                data.append(
                    '<li class="dir">'
                        '<span class="type">[DIR]</span> '
                        '<a href="%s/">%s</a>'
                    '</li>' % (parse.quote(item), html.escape(item))
                )
            else:
                size = os.path.getsize(path)
                for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
                    if size < 1024: break
                    size = size / 1024
                if isinstance(size, float):
                    size = '%.2f' % size
                url = parse.quote(item)
                isVideo = is_video(item)
                hasVideos = hasVideos or isVideo
                tpl = ''.join((
                    '<li class="file',
                    ' file-video' if isVideo else '',
                    '">',
                        '<span class="type">[%s%s]</span> ',
                        '<button class="btn-play">Play</button> ' if isVideo else '',
                        '<a class="link" href="%s">%s</a>',
                    '</li>',
                ))
                args = [size, unit]
                args.extend([url, html.escape(item)])
                args = tuple(args)
                files.append(tpl % args)
        data.extend(files)
        if null:
            data.append('<li>Null</li>')
        data.append('</ul>')
        if hasVideos:
            dataHtml.append(template.render(name='video'))
        dataHtml.extend(data)
        self.headers['Content-Type'] = 'text/html'
        self.write(template.render(
            title = 'Directory Listing',
            head = (
                '<style>'
                    'ul{margin:0;padding-left:20px;line-height:2;}'
                    'li a{word-break:break-all;}'
                    'li.dir{font-weight:bold;}'
                '</style>'
            ),
            header = 'Directory listing for ' + (dir_path or '/'),
            body = ''.join(dataHtml)
        ))
        return True
