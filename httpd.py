#!python
# coding=utf-8
# Author: Gerald <gera2ld@163.com>
# Require: Python 3.4+
import sys,asyncio,locale,email.parser,http.client,urllib.parse,os,io,gzip,logging,time,stat,re
from . import fcgi
PAGE_HEADER="<!DOCTYPE html><html><head>\
<meta name=viewport content='width=device-width'>\
<meta charset=utf-8><title>%s</title><style>\
body{font-family:Tahoma;background:#eee;color:#333;}\
a{text-decoration:none;}\
a:hover{text-decoration:underline;}\
ul{margin:0;padding-left:20px;}\
li a{display:block;word-break:break-all;}\
</style></head><body><h1>%s</h1>"
PAGE_FOOTER='<hr>%s<center>&copy; 2014 Gerald</center></body></html>'
GMT='%a, %d %b %Y %H:%M:%S GMT'

class ChunkedBuffer:
	chunked=False
	def __init__(self,init_flush,writer,bufsize):
		self.init_flush=init_flush
		self.writer=writer
		self.bufsize=bufsize
		self.first_flush=True
		self.buffer=io.BytesIO()
		self.clear()
		self.stream=self.buffer	# can be wrapped
		self.content_encoding='deflate'
	def clear(self):
		self.buffer.seek(0)
		self.buffer.truncate(0)
		self.bytes_sent=0
		self.more=True
		self.error=None
	def wrap_gzip(self,compressLevel=6):
		self.stream=gzip.open(self.buffer,'wb',compressLevel)
		self.content_encoding='gzip'
	@asyncio.coroutine
	def write(self, data):
		if self.error: return
		l=self.stream.write(data)
		self.stream.flush()
		if self.length()>=self.bufsize:
			self.more=True
			yield from self.flush()
	def send(self, data):
		if self.error: return
		self.writer.write(data)
		self.bytes_sent+=len(data)
	@asyncio.coroutine
	def flush(self):
		if self.first_flush:
			self.first_flush=False
			self.init_flush()
		l=self.length()
		if l:
			if self.chunked:
				self.send(('%x\r\n' % l).encode())
			self.send(self.buffer.getvalue())
			if self.chunked:
				self.send(b'\r\n')
			self.buffer.truncate(0)
			self.buffer.seek(0)
			yield from self.writer.drain()
	@asyncio.coroutine
	def close(self):
		self.more=False
		yield from self.flush()
		if self.chunked:
			self.send(b'0\r\n\r\n')
		yield from self.writer.drain()
	def length(self):
		return self.buffer.tell()

class FileProducer:
	def __init__(self, path, bufsize, start=0):
		self.bufsize=bufsize
		self.fp=open(path,'rb')
		if start: self.fp.seek(start)
	def __iter__(self):
		return self
	def __next__(self):
		data=self.fp.read(self.bufsize)
		if data:
			return data
		else:
			raise StopIteration

class HTTPHandler:
	bufsize=8192
	encoding=sys.getdefaultencoding()
	sys_locale=locale.getdefaultlocale()
	server_version='GeHTTPD/1.0'
	sys_version = "Python/" + sys.version.split()[0]
	protocol_version='HTTP/1.1'
	responses={
		100: 'Continue',
		101: 'Switching Protocols',
		200: 'OK',
		201: 'Created',
		202: 'Accepted',
		203: 'Non-Authoritative Information',
		204: 'No Content',
		205: 'Reset Content',
		206: 'Partial Content',
		300: 'Multiple Choices',
		301: 'Moved Permanently',
		302: 'Found',
		303: 'See Other',
		304: 'Not Modified',
		305: 'Use Proxy',
		307: 'Temporary Redirect',
		400: 'Bad Request',
		401: 'Unauthorized',
		402: 'Payment Required',
		403: 'Forbidden',
		404: 'Not Found',
		405: 'Method Not Allowed',
		406: 'Not Acceptable',
		407: 'Proxy Authentication Required',
		408: 'Request Timeout',
		409: 'Conflict',
		410: 'Gone',
		411: 'Length Required',
		412: 'Precondition Failed',
		413: 'Request Entity Too Large',
		414: 'Request-URI Too Long',
		415: 'Unsupported Media Type',
		416: 'Requested Range Not Satisfiable',
		417: 'Expectation Failed',
		428: 'Precondition Required',
		429: 'Too Many Requests',
		431: 'Request Header Fields Too Large',
		500: 'Internal Server Error',
		501: 'Not Implemented',
		502: 'Bad Gateway',
		503: 'Service Unavailable',
		504: 'Gateway Timeout',
		505: 'HTTP Version Not Supported',
		511: 'Network Authentication Required',
		}
	def __init__(self, reader, writer):
		self.reader=reader
		self.writer=writer
		self.conf=writer.transport._server.conf
		self.mime=writer.transport._server.mime
		self.fcgi_handlers=writer.transport._server.fcgi_handlers
		self.remote_addr=writer.get_extra_info('peername')
		self.local_addr=writer.get_extra_info('sockname')
		env=self.base_environ={}
		env['GATEWAY_INTERFACE'] = 'CGI/1.1'
		env['SERVER_ADDR']=self.local_addr[0]
		env['SERVER_PORT']=str(self.local_addr[1])
		env['REMOTE_ADDR']=self.remote_addr[0]
		env['REMOTE_PORT']=str(self.remote_addr[1])
		env['CONTENT_LENGTH']=''
		env['SCRIPT_NAME']=''
		asyncio.async(self.handle())
	def rewrite_path(self,path=None):
		def sub_url(m):
			def sub_items(m):
				k=int(m.group(1) or m.group(2))
				if k>0 and k<=l:
					return items[k-1]
				else:
					return ''
			items=m.groups()
			l=len(items)
			return re.sub(r'\$(?:(\d+)|\{(\d+)\})',sub_items,rule[1])
		if path is None: path=self.path
		for rule in self.conf.get_rewrite(self.host):
			p,n=rule[0].subn(sub_url,path)
			if n>0:
				path=urllib.parse.urljoin(path,p)
				break
		self.environ['DOCUMENT_URI']=path
		path,_,query=path.partition('?')
		# TODO add PATH_INFO
		self.environ['SCRIPT_NAME']=self.path=urllib.parse.unquote(path)
		self.environ['QUERY_STRING']=query
		logging.debug('Rewrited path: %s',path)
	def get_real_path(self,path=None):
		if path is None: path=self.path
		path=os.path.normpath(path).replace('\\','/')
		f=path+'/'
		realpath=None
		for i in self.conf.get_alias(self.host):
			if f.startswith(i[0]):
				realpath=os.path.join(i[1],path[len(i[0]):]).replace('\\','/')
				break
		self.real_path=realpath
		logging.debug('Real path: %s',realpath)
	def send_response_only(self, code, message=None):
		"""Send the response header only."""
		if message is None:
			if code in self.responses:
				message = self.responses[code][0]
			else:
				message = ''
		if self.request_version != 'HTTP/0.9':
			if not hasattr(self, '_headers_buffer'):
				self._headers_buffer = []
			self._headers_buffer.append(("%s %d %s\r\n" %
					(self.protocol_version, code, message)).encode(
						'latin-1', 'strict'))
	def send_header(self, keyword, value):
		"""Send a MIME header to the headers buffer."""
		if self.request_version != 'HTTP/0.9':
			if not hasattr(self, '_headers_buffer'):
				self._headers_buffer = []
			self._headers_buffer.append(
				("%s: %s\r\n" % (keyword, value)).encode('latin-1', 'strict'))

		if keyword.lower() == 'connection':
			if value.lower() == 'close':
				self.close_connection = 1
			elif value.lower() == 'keep-alive':
				self.close_connection = 0
	def end_headers(self):
		"""Send the blank line ending the MIME headers."""
		if self.request_version != 'HTTP/0.9':
			self._headers_buffer.append(b"\r\n")
			self.flush_headers()
	def flush_headers(self):
		if hasattr(self, '_headers_buffer'):
			self.writer.write(b"".join(self._headers_buffer))
			self._headers_buffer = []
	def version_string(self):
		"""Return the server software version string."""
		return self.server_version + ' ' + self.sys_version
	def date_time_string(self, timestamp=None):
		if timestamp is None:
			timestamp = time.time()
		return time.strftime(GMT,time.localtime(timestamp))
	def date_time_compare(self, t1, t2):
		if isinstance(t1,str): t1=time.mktime(time.strptime(t1,GMT))
		if isinstance(t2,str): t2=time.mktime(time.strptime(t2,GMT))
		return t1>=t2
	def send_headers(self):
		if self.protocol_version>='HTTP/1.1' and self.request_version>='HTTP/1.1':
			self.close_connection=self.environ.get('HTTP_CONNECTION','keep-alive')!='keep-alive'
			self.chunked=True	# only allowed in HTTP/1.1
			if 'Content-Length' in self.headers:
				if self.buffer.content_encoding=='deflate':
					self.chunked=False
				else:
					del self.headers['Content-Length']
		else:
			self.chunked=False
			self.close_connection=self.environ.get('HTTP_CONNECTION','close')!='keep-alive'
		if not self.buffer.more:
			self.chunked=False
			self.headers['Content-Length']=str(self.buffer.length())
		elif self.chunked:
			self.headers['Transfer-Encoding']='chunked'
		else:
			self.close_connection=1
		self.headers['Connection']='close' if self.close_connection else 'keep-alive'
		self.headers.add_header('Server',self.version_string())
		self.headers.add_header('Date',self.date_time_string())
		# send headers
		self.send_response_only(*self.status)
		for k,v in self.headers.items(): self.send_header(k,v)
		self.end_headers()
		self.headers_sent=True
		self.buffer.chunked=self.chunked

	@asyncio.coroutine
	def find_file(self, path=None, indexes=[]):
		if path is None:
			path=self.real_path
		if path and self.environ['SCRIPT_NAME'].endswith('/'):
			for index in indexes:
				path=os.path.join(path,index)
				if os.path.isfile(path):
					path=path
					self.environ['SCRIPT_NAME']+=index
					break
			else:
				yield from self.list_dir(path)
				return
		if path and os.path.isdir(path):
			yield from self.redirect(self.environ['SCRIPT_NAME']+'/')
		elif not path or not os.path.isfile(path):
			yield from self.send_error(404)
		else:
			return path
	@asyncio.coroutine
	def write(self, data):
		if self.first_write:
			self.first_write=False
			for i in map(lambda x:x.split(';',1),self.environ.get('HTTP_ACCEPT_ENCODING','').split(',')):
				if i[0]=='gzip':
					ct=self.headers.get('Content-Type','')
					for c in self.conf.get_gzip():
						if ct.startswith(c):
							self.headers.add_header('Content-Encoding','gzip')
							self.buffer.wrap_gzip()
							break
					break
		if self.command!='HEAD':
			if isinstance(data,str):
				data=data.encode('utf-8','ignore')
			if isinstance(data,bytes):
				yield from self.buffer.write(data)
			else:
				for chunk in data:
					yield from self.buffer.write(chunk)
	@asyncio.coroutine
	def parse_request(self):
		self.command = None  # set in case of error on the first line
		self.request_version = version = self.protocol_version
		self.close_connection = 1
		requestline=yield from asyncio.wait_for(self.reader.readline(), self.conf.timeout)
		self.requestline=requestline.strip().decode()
		words=self.requestline.split()
		if len(words) == 3:
			command, path, version = words
			if version[:5] != 'HTTP/':
				yield from self.send_error(400, "Bad request version (%r)" % version)
				return False
			try:
				base_version_number = version.split('/', 1)[1]
				version_number = base_version_number.split(".")
				if len(version_number) != 2:
					raise ValueError
				version_number = int(version_number[0]), int(version_number[1])
			except (ValueError, IndexError):
				yield from self.send_error(400, "Bad request version (%r)" % version)
				return False
			if version_number >= (1, 1) and self.protocol_version >= "HTTP/1.1":
				self.close_connection = 0
			if version_number >= (2, 0):
				yield from self.send_error(505,
						  "Invalid HTTP Version (%s)" % base_version_number)
				return False
		elif not words:
			return False
		else:
			yield from self.send_error(400, "Bad request syntax (%r)" % self.requestline)
			return False

		self.command, self.path, self.request_version = command, path, version
		# Examine the headers and look for a Connection directive.
		headers=[]
		while True:
			line=yield from asyncio.wait_for(self.reader.readline(), self.conf.timeout)
			if not line.strip(): break
			headers.append(line.decode())
		try:
			self._headers=email.parser.Parser(
					_class=http.client.HTTPMessage).parsestr(''.join(headers))
		except http.client.LineTooLong:
			self.send_error(400, "Line too long")
			return False

		conntype = self._headers.get('Connection', "")
		if conntype.lower() == 'close':
			self.close_connection = 1
		elif (conntype.lower() == 'keep-alive' and
			  self.protocol_version >= "HTTP/1.1"):
			self.close_connection = 0
		return True
	@asyncio.coroutine
	def handle(self):
		self.close_connection=1
		while True:
			try:
				yield from self.handle_one_request()
			except (asyncio.TimeoutError,ConnectionAbortedError):
				break
			except:
				import traceback
				traceback.print_exc()
				break
			if self.close_connection: break
		self.writer.close()
	@asyncio.coroutine
	def handle_one_request(self):
		self.status=200,'OK'
		self.error=0
		self.headers_sent=False
		self.headers=http.client.HTTPMessage()
		self.first_write=True
		r=yield from self.parse_request()
		if not r: return
		env=self.environ=self.base_environ.copy()
		env['SERVER_PROTOCOL']=self.request_version
		env['REQUEST_METHOD']=self.command
		env['CONTENT_TYPE']=self._headers.get('Content-Type')
		env['CONTENT_LENGTH']=self._headers.get('Content-Length')
		for k, v in self._headers.items():
			k=k.replace('-','_').upper(); v=v.strip()
			if k in env: continue
			k='HTTP_'+k
			if k in env:
				env[k] += ','+v	 # comma-separate multiple headers
			else:
				env[k] = v
		env['REQUEST_URI']=self.path
		self.host=env.get('HTTP_HOST')
		if self.host:
			i=self.host.find(':')
			if i>0: self.host=self.host[:i]
		self.buffer=ChunkedBuffer(self.send_headers,self.writer,self.bufsize)
		# SCRIPT_NAME and QUERY_STRING will be set after REWRITE
		self.rewrite_path()
		self.get_real_path()
		yield from self.handle_file()
		yield from self.buffer.close()
		logging.info('%s "%s" %d %d', env.get('HTTP_HOST','-'),
				self.requestline, self.status[0], self.buffer.bytes_sent)
	@asyncio.coroutine
	def handle_file(self, path=None):
		path=yield from self.find_file(path,self.conf.get_default(self.host))
		if path is None: return
		_,ext=os.path.splitext(path)
		if ext: ext=ext[1:]
		# FCGI
		eh=self.conf.get_fcgi().get(ext)
		if eh:
			self.headers['Content-Type']='text/html'
			yield from self.fcgi_handle(path,eh)
			return
		# File
		ct=self.mime.get(ext)
		if ct:
			if ct[1]:
				mt=os.stat(path)[stat.ST_MTIME]
				self.headers['Cache-Control']='max-age=%d, must-revalidate' % ct[1]
				self.headers['Last-Modified']=self.date_time_string(mt)
				lm=self.environ.get('HTTP_IF_MODIFIED_SINCE')
				if lm and self.date_time_compare(lm,mt):
					self.status=304,
					return
			self.headers['Content-Type']=ct[0]
			yield from self.send_file(path)
		else:
			self.headers['Content-Type']=self.mime[None][0]
			yield from self.write_bin(path)
	@asyncio.coroutine
	def send_file(self, path=None, start=None, length=None):
		if path is None:
			path=yield from self.find_file(path)
			if path is None: return
		if length is None: length=os.path.getsize(path)
		self.headers['Content-Length']=str(length)
		yield from self.write(FileProducer(path,self.bufsize,start))
	@asyncio.coroutine
	def write_bin(self, path=None):
		if path is None:
			path=yield from self.find_file(path)
			if path is None: return
		self.headers['Content-Type']=self.mime[None][0]
		self.headers.add_header('Content-Disposition','attachment',
				filename=os.path.basename(path).encode(self.encoding).decode('latin-1'))
		self.headers['Accept-Ranges']='bytes'
		fs=os.path.getsize(path)
		if 'HTTP_RANGE' in self.environ:	# self.protocol_version>='HTTP/1.1' and self.request_version>='HTTP/1.1':
			a0,a1=self.environ['HTTP_RANGE'][6:].split('-',1)
			try:
				a0=int(a0)
				a1=int(a1) if a1 else fs-1
				assert(a0<=a1)
				l=a1-a0+1
			except:
				self.send_error(400)
			else:
				self.headers['Content-Range']='bytes %d-%d/%d' % (a0,a1,fs)
				self.headers['Last-Modified']=self.date_time_string(os.stat(path)[stat.ST_MTIME])
				self.status=206,
				yield from self.send_file(path,a0,l)
		else:
			yield from self.send_file(path,length=fs)
	@asyncio.coroutine
	def redirect(self, url, code=303, message=None):
		self.status=code,
		self.headers['Location']=url
		if message is None:
			message='The URL has been moved <a href="%s">here</a>.' % url
		yield from self.write(message)
	@asyncio.coroutine
	def send_error(self, code, message=None):
		p=None
		if not self.error:
			self.error=code
			self.status=code,self.responses.get(code,'???')
			for i in self.conf.get_errdocs(self.host):
				if code>=i[0][0] and code<=i[0][1]:
					p=i[1]
					self.rewrite_path(p)
					self.get_real_path()
					yield from self.handle_file(self.real_path)
					break
		if p is None and code >= 200 and code not in (204, 304):
			self.headers['Content-Type']='text/html'
			if message is None: message=self.responses.get(code,'???')
			yield from self.write(PAGE_HEADER % ('Error...','Error response'))
			yield from self.write('<p>Error code: %d</p><p>Message: %s</p>' % (code,message))
			yield from self.write(PAGE_FOOTER % '')
	@asyncio.coroutine
	def list_dir(self, rpath, pre=''):
		try: d=sorted(os.listdir(rpath),key=type(rpath).upper)
		except:
			yield from self.send_error(404)
			return
		dpath=self.path.rstrip('/')
		yield from self.write(PAGE_HEADER % ('Directory listing for '+dpath,'Directory Listing'))
		ds=dpath.split('/')
		last=ds.pop()
		dirs=[]
		for i in ds:
			pre+=urllib.parse.quote(i)+'/'
			dirs.append('<a href="%s">%s</a>' % (pre, i or 'Home'))
		pre+=urllib.parse.quote(last)+'/'
		dirs.append(last or 'Home')
		guide='/'.join(dirs)
		yield from self.write(guide)
		yield from self.write('<hr><ul>')
		null=True
		files=[]
		for i in d:
			null=False
			p=os.path.join(rpath, i)
			if os.path.isdir(p):
				yield from self.write('<li><a href="%s/"><b>&lt;%s&gt;</b></a></li>' % (pre+urllib.parse.quote(i),i))
			else:
				files.append('<li><a href="%s%s">%s</a></li>' % (pre,urllib.parse.quote(i),i))
		for i in files:
			null=False
			yield from self.write(i)
		if null:
			yield from self.write('<li>Null</li>')
		yield from self.write('</ul>')
		yield from self.write(PAGE_FOOTER % guide)

	@asyncio.coroutine
	def fcgi_write(self, data):
		i=0
		while self.first_write:
			j=data.find(b'\n',i)
			h=data[i:j].strip().decode()
			i=j+1
			if not h:
				data=data[i:]
				break
			k,v=h.split(':',1)
			v=v.strip()
			if k.upper()=='STATUS':
				c,_,m=v.partition(' ')
				self.status=(int(c),m)
			else:
				self.headers[k]=v
		yield from self.write(data)
	@asyncio.coroutine
	def fcgi_err(self, data):
		if isinstance(data,bytes):
			data=data.decode(self.encoding,'replace')
		logging.warning(data)
	@asyncio.coroutine
	def fcgi_handle(self, path, proxy_pass):
		self.environ.update({
			'SCRIPT_FILENAME':os.path.abspath(path),
			'DOCUMENT_ROOT':os.path.abspath(self.conf.get_root(self.environ.get('HTTP_HOST'))),
			'SERVER_NAME':self.host or '',
			'SERVER_SOFTWARE':self.server_version,
			'REDIRECT_STATUS':self.status[0],
			})
		# FCGI works in a single thread, so just one request for one application
		handler=self.fcgi_handlers.get(proxy_pass)
		if handler is None:
			handler=self.fcgi_handlers[proxy_pass]=fcgi.FCGIRequest(proxy_pass)
		l=0
		if self.environ['REQUEST_METHOD']=='POST':
			try: l=int(self.environ['CONTENT_LENGTH'])
			except: pass
		if l:
			data=yield from asyncio.wait_for(self.reader.read(l), self.conf.timeout)
		else:
			data=None
		try:
			yield from handler.fcgi_run(
				self.fcgi_write, self.fcgi_err,
				filter(lambda x:not x[0].startswith('gehttpd.'),self.environ.items()),
				data
			)
		except ConnectionRefusedError:
			yield from self.send_error(500, "Failed connecting to FCGI server!")
