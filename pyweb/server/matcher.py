import re
from ..handlers import FileHandler, DirectoryHandler, FCGIHandler

def error_handler(code):
    if code > 300 and code <= 999:
        def handle(handler):
            handler.send_error(code)
        return handle

handlers = {
    'file': FileHandler(),
    'dir': DirectoryHandler(),
    'fcgi': FCGIHandler(),
}

def test_host(rule):
    reg = re.compile(rule.replace('.', r'\.').replace('*', '.*'))
    def test(request):
        hostname = request.hostname
        return reg.search(hostname) is not None
    return test

def test_path(rule):
    if rule.startswith('~'):
        reg = re.compile(rule[1:])
        def test(request):
            path = request.path
            return reg.search(path) is not None
    elif rule.startswith('='):
        def test(request):
            path = request.path
            return path == rule
    elif rule.startswith('/'):
        if rule.endswith('/'):
            rule = rule[:-1]
        rule_slash = rule + '/'
        def test(request):
            path = request.path
            return path == rule or path.startswith(rule_slash)
    else:
        print('Invalid rule:', rule)
        return
    return test

def normalize_config(items, parent_options=None):
    if not isinstance(items, list):
        items = [items]
    nitems = []
    for item in items:
        item = normalize_config_item(item, parent_options)
        if item:
            nitems.append(item)
    return nitems

def normalize_match(match):
    if not match:
        return
    if isinstance(match, str):
        match = [match]
    tests = []
    for item in match:
        pre, _, rule = item.partition(':')
        test = None
        if pre == 'h':
            test = test_host(rule)
        elif pre == 'p':
            test = test_path(rule)
        if test:
            tests.append(test)
    if tests:
        return tests

def normalize_config_item(config, parent_options=None):
    if not config:
        return
    # name of built-in handlers
    if isinstance(config, str):
        return handlers.get(config)
    # error code
    if isinstance(config, int):
        return error_handler(config)
    # nested config
    if isinstance(config, dict):
        options = {}
        if parent_options is not None:
            options.update(parent_options)
        section_options = config.get('options')
        if section_options is not None:
            options.update(section_options)
        config['options'] = options
        config['handler'] = normalize_config(config.get('handler'), options)
        config['match'] = normalize_match(config.get('match'))
        return config

def match_request(request, match):
    if match is not None:
        for test in match:
            if test(request):
                break
        else:
            return False
    return True

def iter_handlers(request, config, options={}):
    if callable(config):
        yield config, options
    elif isinstance(config, list):
        for item in config:
            yield from iter_handlers(request, item, options)
    elif isinstance(config, dict):
        port = config.get('port')
        match = config.get('match')
        handler = config.get('handler')
        options = config.get('options')
        if (port is None or request.port is None or request.port == port) and match_request(request, match):
            yield from iter_handlers(request, handler, options)
