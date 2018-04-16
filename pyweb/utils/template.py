'''Render templates'''

import os
from jinja2 import Template

BASE_DIR = os.path.join(os.path.dirname(__file__), '../templates')
cache = {}

def get_template(dirname, name):
    '''Compile template based on name or filename'''
    key = dirname, name
    template = cache.get(key)
    if template is None:
        filename = os.path.join(dirname, name + '.html')
        filename = os.path.realpath(filename)
        template = cache.get(filename)
        if template is None:
            raw = open(filename, encoding='utf-8').read()
            template = Template(raw).render
            cache[filename] = template
        cache[key] = template
    return template

def render(name='base', args={}, dirname=BASE_DIR):
    '''Render template based on name or filename'''
    template = get_template(dirname, name)
    if template is None:
        return 'Not found'
    return template(**args)
