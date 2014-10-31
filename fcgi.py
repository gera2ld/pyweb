#!python
# coding=utf-8
# Compatible with Python 2
import struct,io,logging,asyncio

class FCGI:
	FCGI_MAX_LENGTH=0xffff
	FCGI_BEGIN_REQUEST=1
	FCGI_END_REQUEST=3
	FCGI_PARAMS=4
	FCGI_STDIN=5
	FCGI_STDOUT=6
	FCGI_STDERR=7
	def __init__(self,proxy_pass,write=None,write_error=None):
		self.write=write
		self.write_error=write_error
		self.reqid=1
		self.proxy_pass=proxy_pass
	@asyncio.coroutine
	def connect(self):
		host,port=self.proxy_pass
		self.con=asyncio.open_connection(host=host, port=port)
		self.reader,self.writer=yield from asyncio.wait_for(self.con, 5)
	def build_record(self, t, data=None, rec=None, empty=True):
		if rec is None: rec=[]
		if isinstance(data,tuple):
			f,L=data
		elif data:
			f,L=io.BytesIO(data),len(data)
		else:
			f=L=0
		while True:
			l=min(self.FCGI_MAX_LENGTH,L)
			data=f.read(l) if l else b''
			p=(8-l%8)%8
			if l or empty: rec.append(struct.pack('!BBHHBB%ds' % (l+p),1,t,self.reqid,l,p,0,data))
			if not l: break
			L-=l
		return rec
	def build_data(self,env):
		d=[]
		for k,v in env:
			k=k.encode()
			v=str(v).encode()
			for l in (len(k),len(v)):
				if l>127: d.append(struct.pack('!L',l|0x80000000))
				else: d.append(struct.pack('B',l))
			d.append(k)
			d.append(v)
		return b''.join(d)
	@asyncio.coroutine
	def fcgi_parse(self):
		while True:
			h=yield from self.reader.read(8)
			v,t,reqid,l,p,x=struct.unpack('!BBHHBB',h)
			d=yield from self.reader.read(l)
			yield from self.reader.read(p)
			if reqid!=self.reqid: continue
			if t==self.FCGI_END_REQUEST:
				#sapp,spro=struct.unpack('!IB3x',d)
				break
			else:
				if t==self.FCGI_STDOUT:
					write=self.write
				elif t==self.FCGI_STDERR:
					write=self.write_error
				else:
					logging.warning(t)
					write=None
				if write:
					yield from write(d)
	@asyncio.coroutine
	def fcgi_run(self,env,data):
		r=self.build_record(self.FCGI_BEGIN_REQUEST,struct.pack('!HB5x',1,0),empty=False)
		self.build_record(self.FCGI_PARAMS,self.build_data(env),r)
		self.build_record(self.FCGI_STDIN,data,r)
		r=b''.join(r)
		self.writer.write(r)
		yield from self.writer.drain()
		yield from self.fcgi_parse()
