import time

GMT = '%a, %d %b %Y %H:%M:%S GMT'

def datetime_string(timestamp=None):
    if timestamp is None:
        timestamp = time.time()
    return time.strftime(GMT, time.localtime(timestamp))

def datetime_compare(t1, t2):
    if isinstance(t1, str):
        t1 = time.mktime(time.strptime(t1, GMT))
    if isinstance(t2, str):
        t2 = time.mktime(time.strptime(t2, GMT))
    return t1 >= t2
