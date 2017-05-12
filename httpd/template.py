'''Render templates'''

import os

_TEMPLATES = {}

def _read_data(directory=os.path.join(os.path.dirname(__file__), 'templates')):
    for k in os.listdir(directory):
        if not k.endswith('.html'):
            continue
        name = k[:-5]
        _TEMPLATES[name] = open(os.path.join(directory, k), encoding='utf-8').read()

_read_data()

def render(name='base', **kw):
    '''Render template based on name'''
    args = {
        'title': kw.get('title', 'Super Light HTTP Daemon'),
        'head': kw.get('head', ''),
        'header': kw.get('header') or kw.get('title', 'Super Light HTTP Daemon'),
        'body': kw.get('body', 'Hello world'),
        'footer': kw.get('footer', ''),
    }
    return _TEMPLATES.get(name, '') % args
