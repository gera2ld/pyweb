'''
FastCGI module
'''
import struct
import io
import asyncio
from .parser import parse_addr

# Reference:
# http://www.fastcgi.com/drupal/node/6?q=node/22
FCGI_MAX_LENGTH = 0xffff
# Value for version component of FCGI_Header
FCGI_VERSION_1 = 1
# Values for type component of FCGI_Header
FCGI_BEGIN_REQUEST = 1
FCGI_ABORT_REQUEST = 2
FCGI_END_REQUEST = 3
FCGI_PARAMS = 4
FCGI_STDIN = 5
FCGI_STDOUT = 6
FCGI_STDERR = 7
FCGI_DATA = 8
FCGI_GET_VALUES = 9
FCGI_GET_VALUES_RESULT = 10
FCGI_UNKNOWN_TYPE = 11
FCGI_MAXTYPE = FCGI_UNKNOWN_TYPE
# Value for requestId component of FCGI_Header
FCGI_NULL_REQUEST_ID = 0
# Mask for flags component of FCGI_BeginRequestBody
FCGI_KEEP_CONN = 1
# Values for role component of FCGI_BeginRequestBody
FCGI_RESPONDER = 1
FCGI_AUTHORIZER = 2
FCGI_FILTER = 3
# Values for protocolStatus component of FCGI_EndRequestBody
FCGI_REQUEST_COMPLETE = 0
FCGI_CANT_MPX_CONN = 1
FCGI_OVERLOADED = 2
FCGI_UNKNOWN_ROLE = 3
# Variable names for FCGI_GET_VALUES / FCGI_GET_VALUES_RESULT records
FCGI_MAX_CONNS = 'FCGI_MAX_CONNS'
FCGI_MAX_REQS = 'FCGI_MAX_REQS'
FCGI_MPXS_CONNS = 'FCGI_MPXS_CONNS'

def build_record(req_id, rec_type, data=None, allow_empty=True):
    '''Build record into a list of bytes'''
    if isinstance(data, tuple):
        stream, length = data
    elif data:
        stream, length = io.BytesIO(data), len(data)
    else:
        stream, length = None, 0
    while True:
        buf_len = min(FCGI_MAX_LENGTH, length)
        data = stream.read(buf_len) if buf_len else b''
        pad = (8 - buf_len % 8) % 8
        if buf_len or allow_empty:
            yield struct.pack(
                '!BBHHBx', FCGI_VERSION_1, rec_type, req_id, buf_len, pad)
            if buf_len:
                yield data
            if pad:
                yield struct.pack('%dx' % pad)
        if not buf_len:
            break
        length -= buf_len

def build_name_value_pairs(pairs):
    '''Build key-value pairs into a byte sequence.'''
    data = []
    for key, value in pairs:
        key = key.encode()
        value = str(value).encode()
        for length in (len(key), len(value)):
            if length > 127:
                data.append(struct.pack('!L', length | 0x80000000))
            else:
                data.append(struct.pack('B', length))
        data.append(key)
        data.append(value)
    return b''.join(data)

class Worker:
    '''FastCGI worker via a connection.'''

    def __init__(self, addr, req_id):
        self.addr = addr
        self.req_id = req_id
        self.reader = self.writer = None

    def close(self):
        '''Close connection.'''
        if self.writer:
            self.writer.close()
            self.writer = None

    async def connect(self):
        '''Connect to FastCGI server.'''
        host, port = self.addr
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(host=host, port=port), 5)

    async def fcgi_parse(self, write_out, write_err, timeout):
        '''Parse a FastCGI response and pipe to clients.'''
        while True:
            header = await asyncio.wait_for(self.reader.readexactly(8), timeout)
            version, rec_type, res_id, length, padding = struct.unpack(
                '!BBHHBx', header)
            data = await asyncio.wait_for(self.reader.readexactly(length), timeout)
            await asyncio.wait_for(self.reader.readexactly(padding), timeout)
            if version != FCGI_VERSION_1 or res_id != self.req_id:
                continue
            if rec_type == FCGI_END_REQUEST:
                #sapp, spro = struct.unpack('!IB3x', data)
                break
            else:
                if rec_type == FCGI_STDOUT:
                    write = write_out
                # elif rec_type == FCGI_STDERR:
                else:
                    write = write_err
                write(data)

    async def fcgi_run(self, write_out, write_err, reader, env, timeout):
        '''Run FastCGI

        - write_out
        - write_err
        - reader: wsgi.input
        - env: environment variables
        - timeout
        '''
        rec = []
        rec.extend(build_record(
            self.req_id, FCGI_BEGIN_REQUEST,
            struct.pack('!HB5x', FCGI_RESPONDER, FCGI_KEEP_CONN),
            False,
        ))
        rec.extend(build_record(
            self.req_id, FCGI_PARAMS,
            build_name_value_pairs((k, v) for k, v in env.items() if not k.startswith('gehttpd.')),
        ))
        length = 0
        if env['REQUEST_METHOD'] == 'POST':
            try:
                length = int(env['CONTENT_LENGTH'])
            except ValueError:
                pass
        while length > 0:
            readlen = min(FCGI_MAX_LENGTH, length)
            data = await asyncio.wait_for(reader.read(readlen), timeout)
            rec.extend(build_record(self.req_id, FCGI_STDIN, data, False))
            length -= len(data)
        rec.extend(build_record(self.req_id, FCGI_STDIN))
        res = b''.join(rec)
        if self.writer is None:
            await self.connect()
        self.writer.write(res)
        await self.writer.drain()
        await self.fcgi_parse(write_out, write_err, timeout)

class Dispatcher:
    '''Dispatcher of FastCGI workers.

    PHP on Windows has problems with concurrency
    '''
    max_connection = 1
    pool = {}
    timeout = 30

    def __init__(self, targets):
        self.offset = 0
        self.full = False
        self.queue = asyncio.Queue()
        if isinstance(targets, str):
            targets = [targets]
        self.connections = [[parse_addr(target), 0] for target in targets]

    async def get_worker(self):
        '''Get an available worker from the pool.'''
        worker = None
        if not self.full:
            try:
                worker = self.queue.get_nowait()
            except asyncio.queues.QueueEmpty:
                item = self.connections[self.offset]
                if item[1] >= self.max_connection:
                    self.full = True
                else:
                    worker = Worker(item[0], item[1])
                    item[1] += 1
                    self.offset = (self.offset + 1) % len(self.connections)
        if worker is None:
            worker = await self.queue.get()
        return worker

    async def run_worker(self, write_out, write_err, reader, env):
        '''Get an available worker and pass the arguments.'''
        worker = await self.get_worker()
        try:
            await worker.fcgi_run(write_out, write_err, reader, env, timeout=self.timeout)
        except Exception as exc:
            worker.close()
            raise exc
        finally:
            self.queue.put_nowait(worker)

    @classmethod
    def get(cls, targets):
        '''Get a dispatcher based on FCGI rule.'''
        dispatcher_id = id(targets)
        dispatcher = cls.pool.get(dispatcher_id)
        if dispatcher is None:
            dispatcher = cls.pool[dispatcher_id] = cls(targets)
        return dispatcher

def main():
    '''Start a worker for test use.'''
    loop = asyncio.get_event_loop()
    fcgi = Worker(('127.0.0.1', 9000), 1)
    loop.run_until_complete(fcgi.fcgi_run(print, print, {
        'REQUEST_METHOD': 'GET',
    }, None, 10))

if __name__ == '__main__':
    main()
