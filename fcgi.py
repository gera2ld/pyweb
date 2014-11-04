#!python
# coding=utf-8
import struct,io,asyncio

# Reference:
# http://www.fastcgi.com/drupal/node/6?q=node/22
FCGI_MAX_LENGTH			=0xffff
# Value for version component of FCGI_Header
FCGI_VERSION_1			=1
# Values for type component of FCGI_Header
FCGI_BEGIN_REQUEST		=1
FCGI_ABORT_REQUEST		=2
FCGI_END_REQUEST		=3
FCGI_PARAMS				=4
FCGI_STDIN				=5
FCGI_STDOUT				=6
FCGI_STDERR				=7
FCGI_DATA				=8
FCGI_GET_VALUES			=9
FCGI_GET_VALUES_RESULT	=10
FCGI_UNKNOWN_TYPE		=11
FCGI_MAXTYPE=FCGI_UNKNOWN_TYPE
# Value for requestId component of FCGI_Header
FCGI_NULL_REQUEST_ID	=0
# Mask for flags component of FCGI_BeginRequestBody
FCGI_KEEP_CONN			=1
# Values for role component of FCGI_BeginRequestBody
FCGI_RESPONDER			=1
FCGI_AUTHORIZER			=2
FCGI_FILTER				=3
# Values for protocolStatus component of FCGI_EndRequestBody
FCGI_REQUEST_COMPLETE	=0
FCGI_CANT_MPX_CONN		=1
FCGI_OVERLOADED			=2
FCGI_UNKNOWN_ROLE		=3
# Variable names for FCGI_GET_VALUES / FCGI_GET_VALUES_RESULT records
FCGI_MAX_CONNS			="FCGI_MAX_CONNS"
FCGI_MAX_REQS			="FCGI_MAX_REQS"
FCGI_MPXS_CONNS			="FCGI_MPXS_CONNS"

class FCGI:
	def __init__(self, proxy_pass, req_id):
		self.proxy_pass=proxy_pass
		self.req_id=req_id
		self.reader=self.writer=None
	def build_record(self, type, data=None, allowEmpty=True):
		if isinstance(data,tuple):
			f,L=data
		elif data:
			f,L=io.BytesIO(data),len(data)
		else:
			f=L=0
		while True:
			l=min(FCGI_MAX_LENGTH,L)
			data=f.read(l) if l else b''
			p=(8-l%8)%8
			if l or allowEmpty:
				yield struct.pack('!BBHHBx',
					FCGI_VERSION_1,type,self.req_id,l,p)
				if l: yield data
				if p: yield struct.pack('%dx' % p)
			if not l: break
			L-=l
	def build_name_value_pairs(self,env):
		d=[]
		for k,v in env:
			k=k.encode()
			v=str(v).encode()
			for l in (len(k),len(v)):
				if l>127:
					d.append(struct.pack('!L',l|0x80000000))
				else:
					d.append(struct.pack('B',l))
			d.append(k)
			d.append(v)
		return b''.join(d)
	@asyncio.coroutine
	def connect(self):
		host,port=self.proxy_pass
		self.reader,self.writer=yield from asyncio.wait_for(
				asyncio.open_connection(host=host, port=port), 5)
	@asyncio.coroutine
	def fcgi_parse(self, write_out, write_err):
		while True:
			header=yield from self.reader.read(8)
			version,type,res_id,length,padding=(
					struct.unpack('!BBHHBx',header))
			data=yield from self.reader.read(length)
			yield from self.reader.read(padding)
			if (version!=FCGI_VERSION_1 or res_id!=self.req_id): continue
			if type==FCGI_END_REQUEST:
				#sapp,spro=struct.unpack('!IB3x',data)
				break
			else:
				if type==FCGI_STDOUT:
					write=write_out
				#elif type==FCGI_STDERR:
				else:
					write=write_err
				yield from write(data)
	@asyncio.coroutine
	def fcgi_run(self, write_out, write_err, env, data):
		rec=[]
		rec.extend(self.build_record(FCGI_BEGIN_REQUEST,
				struct.pack('!HB5x',FCGI_RESPONDER,FCGI_KEEP_CONN),
				allowEmpty=False))
		rec.extend(self.build_record(FCGI_PARAMS,
			self.build_name_value_pairs(env)))
		rec.extend(self.build_record(FCGI_STDIN,data))
		r=b''.join(rec)
		if self.writer is None or self.writer._protocol._connection_lost:
			yield from self.connect()
		self.writer.write(r)
		yield from self.writer.drain()
		yield from self.fcgi_parse(write_out,write_err)

class FCGIRequest:
	def __init__(self,proxy_pass,max_con=1):
		# PHP on windows has problems with concurrency
		if os.name=='nt': max_con=1
		self.queue=asyncio.Queue()
		for i in range(1,max_con+1):
			self.queue.put_nowait(FCGI(proxy_pass,i))
	@asyncio.coroutine
	def fcgi_run(self, *k):
		worker=yield from self.queue.get()
		yield from worker.fcgi_run(*k)
		self.queue.put_nowait(worker)
