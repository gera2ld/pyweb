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
