import gzip, io

class BaseWriter:
    def __init__(self, raw, logger):
        self.raw = raw
        self.logger = logger

    def flush(self):
        pass

    def close(self):
        pass

class RawWriter(BaseWriter):
    def __init__(self, raw, logger):
        super().__init__(raw, logger)
        self.written = 0

    def write(self, data):
        self.raw.write(data)
        self.written += len(data)

class ChunkedWriter(BaseWriter):
    '''
    A wrapper to write data into chunks

       Chunked-Body   = *chunk
                        last-chunk
                        trailer
                        CRLF
       chunk          = chunk-size [ chunk-extension ] CRLF
                        chunk-data CRLF
       chunk-size     = 1*HEX
       last-chunk     = 1*("0") [ chunk-extension ] CRLF
       chunk-extension= *( ";" chunk-ext-name [ "=" chunk-ext-val ] )
       chunk-ext-name = token
       chunk-ext-val  = token | quoted-string
       chunk-data     = chunk-size(OCTET)
       trailer        = *(entity-header CRLF)
    '''
    def write(self, data):
        if data:
            #self.logger.debug('chunk %d', len(data))
            self.raw.write(hex(len(data))[2:].encode() + b'\r\n')
            self.raw.write(data)
            self.raw.write(b'\r\n')

    def close(self):
        '''write last chunk'''
        #self.logger.debug('chunk 0')
        self.raw.write(b'0\r\n\r\n')

class BufferedWriter(BaseWriter):
    '''
    A wrapper to buffer data to avoid small pieces of data.
    '''
    bufsize = 4096
    def __init__(self, raw, logger, bufsize = None):
        super().__init__(raw, logger)
        if bufsize:
            self.bufsize = bufsize
        self.buffer = None

    def write(self, data):
        if self.buffer is None:
            self.buffer = io.BytesIO()
        self.buffer.write(data)
        if self.buffer.tell() >= self.bufsize:
            self.flush()

    def flush(self):
        #self.logger.debug('BufferedWriter:flush')
        if self.buffer:
            data = self.buffer.getvalue()
            if data:
                self.raw.write(data)
            self.buffer = None

    def close(self):
        self.flush()
        self.raw.close()

class GZipWriter(BaseWriter):
    def __init__(self, raw, logger, compresslevel = 6):
        super().__init__(raw, logger)
        self.buffer = gzip.open(raw, 'wb', compresslevel = compresslevel)

    def write(self, data):
        self.buffer.write(data)

    def close(self):
        #self.logger.debug('GZipWriter:close')
        #self.buffer.flush()
        self.buffer.close()
        self.raw.flush()
        self.raw.close()
