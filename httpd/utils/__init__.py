from .logger import logger

def parse_addr(hostname, default_host='', default_port=80):
    if hostname.count(':') > 1:
        # IPv6
        if hostname.startswith('['):
            end_offset = hostname.index(']')
            host = hostname[1 : end_offset]
            port = hostname[end_offset + 1 :]
            if port:
                assert port.startswith(':')
                port = port[1:]
        else:
            host = hostname
            port = default_port
    else:
        # IPv4
        host, _, port = hostname.partition(':')
    try:
        port = int(port)
    except:
        port = default_port
    return host, port

class FileProducer:
    bufsize = 4096
    fp = None
    def __init__(self, path, start=0, length=None):
        if length is None or length > 0:
            self.fp = open(path, 'rb')
            if start: self.fp.seek(start)
        self.length = length

    def __iter__(self):
        return self

    def __next__(self):
        if self.fp is None:
            raise StopIteration
        length = min(self.length, self.bufsize) if self.length else self.bufsize
        data = self.fp.read(length)
        if data:
            if self.length:
                self.length -= len(data)
            return data
        else:
            raise StopIteration

    def __del__(self):
        self.close()

    def close(self):
        if self.fp is not None:
            self.fp.close()
            self.fp = None
