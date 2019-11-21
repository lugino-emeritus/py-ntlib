import select
import socket
import time

__version__ = '0.1.1'

_TIMEOUT_MAX = 30  # used for udp or while waiting for a message
_TIMEOUT_TCP = 2  # timeout for connected tcp socket

#-------------------------------------------------------

class ConnectionClosed(ConnectionError):
	"""Peer socket closed"""
	pass
# Error to catch blocking and timeout errors of a socket
BlockingTimeout = (BlockingIOError, socket.timeout)


def _ipv6_check(ip):
	return True if ':' in ip else False if '.' in ip else None


class _EnsureTimeout:
	def __init__(self, sock):
		self.sock = sock
		self.active = False
	def __enter__(self):
		if self.active:
			raise RuntimeError('EnsureTimeout already active')
		self.active = True
		self.org_timeout = self.sock.gettimeout()
	def __exit__(self, *exc_args):
		self.sock.settimeout(self.org_timeout)
		self.active = False


class Socket(socket.socket):
	def __init__(self, sock=None, *, addr=None, ipv6=None, udp=False, timeout=-1):
		"""Create a (tcp) socket with timeout.

		If sock is already a socket a tsocket.Socket will be generated. The origin socket will be closed.
		If sock is an address tuple it will bind to that and set the ip version.
		"""
		init = True
		if sock:
			if isinstance(sock, socket.socket):
				super().__init__(sock.family, sock.type, sock.proto, fileno=sock.detach())
				self.settimeout(sock.gettimeout() if timeout == -1 else timeout)
				init = False
			elif isinstance(sock, tuple):
				addr = sock
			else:
				raise TypeError('sock must be a socket or address (tuple)')

		if init:
			if ipv6 is None and addr:
				ipv6 = _ipv6_check(addr[0])
			super().__init__(socket.AF_INET6 if ipv6 else socket.AF_INET,
					socket.SOCK_DGRAM if udp else socket.SOCK_STREAM)
			self.settimeout(_TIMEOUT_MAX if timeout == -1 else timeout)
			if addr:
				self.bind(addr)

		self._ensure_timeout = _EnsureTimeout(self)
		self._empty_msg_close = (self.type == socket.SOCK_STREAM)
		self.timeout_max = _TIMEOUT_MAX

	def ensure_timeout(self):
		return self._ensure_timeout

	def is_ipv6(self):
		return self.family == socket.AF_INET6

	def data_available(self, timeout=None):
		return select.select((self,), (), (), timeout or self.timeout_max)[0]


	def clear_buffer(self, timeout=1, max_rounds=2**20, *, esc_data=None):
		"""Clear input buffer of socket.

		Returns True if a timeout occurs,
			False if there is more data to read.

		If esc_data is defined then the socket tries to send this data in each round.
			e.g. esc_data=b'\n'; not recommended, but sometimes necessary :(
		"""
		with self._ensure_timeout:
			t_end = time.monotonic() + self.timeout_max
			self.settimeout(timeout)
			try:
				for _ in range(max_rounds):
					if esc_data:
						try:
							self.send(esc_data)
						except BlockingTimeout:
							esc_data = None
					if not self.recv(2**16):
						if self._empty_msg_close:
							raise ConnectionClosed('peer closed: {}'.format(sock))
						return True
					if t_end < time.monotonic():
						return False
			except BlockingTimeout:
				return True
			return False


	def accept(self):
		'''return (tsocket.Socket, addr)'''
		(sock, addr) = super().accept()
		return (self.__class__(sock, timeout=self.timeout), addr)
	def taccept(self, timeout=_TIMEOUT_TCP):
		'''same as accept, but also sets a different timeout'''
		(sock, addr) = super().accept()
		return (self.__class__(sock, timeout=timeout), addr)


	def tsend(self, data):
		'''socket.sendall uses the timeout for all data,
		so if data is very long the timeout could be too short, tsend solves this.
		'''
		t_end = time.monotonic() + self.timeout_max
		tosend = len(data)
		while tosend:
			if tosend < 2**16:
				self.sendall(data[-tosend:])
				break
			tosend -= self.send(data[-tosend:])
			if t_end < time.monotonic():
				raise socket.timeout('tsend max-timeout, not sent: {} bytes'.format(tosend))

	def send_list(self, lst):
		totalen = sum(map(len, lst))
		if totalen < 2**16:
			self.sendall(b''.join(lst))
		else:
			t_end = time.monotonic() + self.timeout_max
			for data in lst:
				tosend = len(data)
				while tosend:
					if t_end < time.monotonic():
						raise socket.timeout('max-timeout')
					if tosend < 2**16:
						self.sendall(data[-tosend:])
						break
					tosend -= self.send(data[-tosend:])
		return totalen


	def recv_exactly(self, size):
		t_end = time.monotonic() + self.timeout_max
		lst = []
		while True:
			data = self.recv(size)
			if not data:
				if self._empty_msg_close:
					raise ConnectionClosed('peer closed: {}'.format(sock))
				return b''
			size -= len(data)
			lst.append(data)
			if not size:
				return b''.join(lst)
			if t_end < time.monotonic():
				raise socket.timeout('max-timeout')

	def recv_until(self, maxlen=2**16, end_char=b'\n'):
		'''Receives all bytes until end_char, not useable with udp'''
		t_end = time.monotonic() + self.timeout_max
		data = bytearray()
		for _ in range(maxlen):
			c = self.recv(1)
			if not c:
				if self._empty_msg_close:
					raise ConnectionClosed('peer closed: {}'.format(sock))
				return b''
			if c == end_char:
				return bytes(data)
			if t_end < time.monotonic():
				raise socket.timeout('max-timeout')
			data.extend(c)
		raise ValueError('end character not found within {} bytes'.format(len(data)))

	def get_hostaddr(self, hostaddr):
		(fam, _, _, _, addr) = socket.getaddrinfo(hostaddr[0], hostaddr[1],
				family=0 if self.is_ipv6() else self.family)[0]
		if fam != self.family:
			if fam == socket.AF_INET and self.is_ipv6():
				return ('::FFFF:'+addr[0], addr[1])
			raise socket.gaierror('no valid socket family found')
		return addr


def get_ipv6_addr(hostaddr):
	(fam, _, _, _, addr) = socket.getaddrinfo(hostaddr[0], hostaddr[1])[0]
	return fam == socket.AF_INET6, addr


def find_free_addr(ports=(0,), ip='', *, ipv6=None, udp=False):
	'''ports is an iterable which should be tested, port 0 results return a free port'''
	if ipv6 is None:
		ipv6 = _ipv6_check(ip)
	for p in ports:
		try:
			with Socket(ipv6=ipv6, udp=udp) as sock:
				sock.bind((ip, p))
				return sock.getsockname()[:2]
		except OSError:
			pass
	return None


def get_server_sock(port, udp=False):
	if socket.has_ipv6:
		sock = Socket(udp=udp, ipv6=True)
		try:
			sock.setsockopt(getattr(socket, 'IPPROTO_IPV6', 41), socket.IPV6_V6ONLY, 0)
		except Exception as e:
			logger.warning('IPV6 sock option not setable: %r', e)
	else:
		sock = Socket(udp=udp)
	sock.bind(('', port))
	return sock


def create_connection(address, timeout=2*_TIMEOUT_TCP, source_address=None):
	sock = socket.create_connection(address, timeout, source_address)
	return Socket(sock, timeout=_TIMEOUT_TCP)
