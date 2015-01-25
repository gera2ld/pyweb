#!python
# coding=utf-8
# Compatible with Python 2
import codecs,collections,os,io,re,logging

class ParseError(Exception): pass

class ConfParser:
	def __init__(self,filename='httpd.conf'):
		self.filename=os.path.expanduser(filename)
	def parse(self):
		self.conf={}
		self.server=None
		self.host=None
		try:
			f=codecs.open(self.filename,encoding='utf-8')
		except:
			pass
		else:
			for line in f:
				line=line.rstrip()
				if not line or line[0]=='#': continue
				try:
					args=self.split_args(line)
					self.parse_conf_line(args)
				except Exception as e:
					logging.error('Error parsing config:\n\t%s\nMessage: %s',line,e)
			f.close()
		return self.conf
	def split_args(self,s,allow_transfer=False):
		# allow_transfer: '\x'=>'x'
		def add_arg():
			m=w.getvalue()
			if m: a.append(m)
			w.truncate(0)
			w.seek(0)
		a=collections.deque()
		r=io.StringIO(s)
		w=io.StringIO()
		q=f=None
		while True:
			c=r.read(1)
			if not c:
				add_arg()
				break
			if q is None:
				if c in '\'"':
					q,c=c,None
				else:
					q=''
			if f:
				if c: w.write(c)
				f=False
			elif c=='\\' and allow_transfer:
				f=True
			else:
				if q: m=q==c
				else: m=c in ' \t'
				if m:
					add_arg()
					q=None
				elif c: w.write(c)
		if q or f: raise ParseError('Error parsing arguments.')
		return a
	def new_server(self,arg=''):
		self.server={
			'hosts':{},
			'fcgi':{},
			'gzip':['text'],
			'timeout':10,
			'threads':40,
			'loglevel':2,
		}
		h,_,p=arg.partition(':')
		if not h: h='0.0.0.0'
		if not p: p='80'
		self.server['server']=h+':'+p
		self.conf.setdefault(p,self.server)
		self.new_host()
		return self.server
	def new_host(self,arg=None):
		hosts=self.server['hosts']
		self.host={
			'rewrite':[],
			'alias':[],
			'headers':[],
			'errdocs':[],
			'default':[],
		}
		if arg is None:
			hosts[None]=self.host
		else:
			for i in arg.split(','): hosts[i]=self.host
		return self.host
	def parse_conf_line(self,args):
		cmd=args.popleft()
		if cmd=='server':
			self.new_server(args.popleft())
			return
		if self.server is None:
			self.new_server('')
		if cmd=='host':
			self.new_host(args.popleft())
		elif cmd=='threads':
			self.server['threads']=int(args.popleft())
		elif cmd=='loglevel':
			self.server['loglevel']=int(args.popleft())
		elif cmd=='fcgi':
			l,_,p=args.popleft().partition(':')
			l=l,int(p)
			d=self.server['fcgi']
			b=args.popleft()
			for i in b.split(','):
				if i: d[i]=l
		elif cmd=='gzip':
			d=self.server['gzip']=[]
			for i in args.popleft().split(','):
				if i.find('/')<0: i+='/'
				d.append(i)
		elif cmd=='rewrite':
			self.host['rewrite'].append((
				re.compile(args.popleft()),
				args.popleft(),
			))
		elif cmd=='alias':
			a=args.popleft().replace('\\','/')
			if not a.endswith('/'): a+='/'
			b=args.popleft().replace('\\','/')
			if not b.endswith('/'): b+='/'
			b=os.path.expanduser(b)
			self.host['alias'].append((a,b))
		elif cmd=='header':
			a=args.popleft().replace('\\','/')
			if not a.endswith('/'): a+='/'
			b=args.popleft()
			c=args.popleft()
			self.host['headers'].append((a,b,c))
		elif cmd=='errdocs':
			i,_,j=args.popleft().partition(',')
			b=args.popleft()
			i=int(i)
			j=int(j) if _ else i
			self.host['errdocs'].append(((i,j),b))
		elif cmd=='default':
			self.host['default']=args.popleft().split(',')
		else:
			raise ParseError('Unknown command: %s' % cmd)

def parse_mime(filename='mime.conf'):
	filename=os.path.expanduser(filename)
	mime={}
	try:
		f=codecs.open(filename,encoding='utf-8')
	except:
		pass
	else:
		for line in f:
			line=line.rstrip()
			if not line or line[0]=='#': continue
			args=list(filter(None,line.split()))
			l=len(args)
			if l<2 or l>3: continue
			try:
				if l==2: args.append(0)
				else: args[2]=int(args[2])
			except:
				continue
			t=args[0],args[2]
			for i in args[1].split(','):
				mime[i]=t
		f.close()
	return mime

class ServerConfig:
	def __init__(self, conf):
		self.conf=conf
		self.timeout=conf.get('timeout',10)
		self.hosts={None:{}}
		hosts=conf.get('hosts',{})
		for i in hosts:
			h=hosts[i]
			H=self.hosts[i]={}
			H['rewrite']=list(map(tuple,h.get('rewrite',[])))
			H['alias']=list(map(tuple,h.get('alias',[])))
			H['headers']=list(map(tuple,h.get('headers',[])))
			H['errdocs']=list(h.get('errdocs',[]))
			H['default']=list(h.get('default',[]))
	def get(self, key, default=None):
		return self.conf.get(key,default)
	def get_rule(self, key, host, default=None, inherit=False):
		h=self.hosts.get(host)
		H=self.hosts.get(None)
		if H is None: inherit=False
		elif h is None: h=H
		if h is None: return default
		r=h.get(key)
		if r is None and inherit and h is not H: r=H.get(key)
		if r is None: r=default
		return r
	def get_rewrite(self, host):
		return self.get_rule('rewrite',host,[])
	def get_alias(self, host):
		return self.get_rule('alias',host,[])
	def get_headers(self, host):
		return self.get_rule('headers',host,[])
	def get_default(self, host):
		return self.get_rule('default',host,[])
	def get_root(self, host):	# for FCGI::DOCUMENT_ROOT
		return self.get_rule('root',host,[])
	def get_errdocs(self, host):
		return self.get_rule('errdocs',host,[])
	def get_fcgi(self):
		return self.conf.get('fcgi',{})
	def get_gzip(self):
		return self.conf.get('gzip',[])

class Config:
	def __init__(self,mime_file=None,conf_file=None):
		self.mime={None:('application/octet-stream',0)}
		if mime_file is None:
			mime_file='~/.gerald/mime.conf'
		self.mime.update(parse_mime(mime_file))
		if conf_file is None:
			conf_file='~/.gerald/httpd.conf'
		self.conf=ConfParser(conf_file).parse()
		self.servers={}
		for p in self.conf:
			self.servers[p]=ServerConfig(self.conf[p])
		self.fcgi_handlers={}
	def get_conf(self, port):
		return self.servers.get(port)
