import os

templates = {}

def read_data():
    dir_tpl = os.path.join(os.path.dirname(__file__), 'templates')
    for k in os.listdir(dir_tpl):
        if not k.endswith('.html'): continue
        name = k[:-5]
        templates[name] = open(os.path.join(dir_tpl, k), encoding='utf-8').read()

read_data()

def render(name='base', **kw):
    args = {
        'title': kw.get('title', 'Super Light HTTP Daemon'),
        'head': kw.get('head', ''),
        'header': kw.get('header') or kw.get('title', 'Super Light HTTP Daemon'),
        'body': kw.get('body', 'Hello world'),
        'footer': kw.get('footer', ''),
    }
    return templates.get(name, '') % args
