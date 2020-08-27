import select
import socket
import time

from socket import (timeout as Timeout, gaierror as GAIError)

__version__ = '0.2.6'

_TIMEOUT_MAX = 30  # used for udp or while waiting for a message
_TIMEOUT_MID = 2  # timeout for connected tcp socket

USE_IPV6 = socket.has_ipv6

#-------------------------------------------------------

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
	def __init__(self, sock=None, *, ipv6=None, udp=False, timeout=None):
		"""Create a (tcp) socket with timeout.

		If sock is already a socket a tsocket.Socket will be generated. The origin socket will be closed.
		If sock is an address tuple it will bind to that and set the ip version.
		"""
		if sock:
			if isinstance(sock, socket.socket):
				super().__init__(sock.family, sock.type, sock.proto, fileno=sock.detach())
				self.settimeout(timeout or sock.gettimeout())
			else:
				raise TypeError('sock must be a socket or None')
		else:
			super().__init__(socket.AF_INET6 if ipv6 else socket.AF_INET,
				socket.SOCK_DGRAM if udp else socket.SOCK_STREAM)
			self.settimeout(timeout or _TIMEOUT_MAX)

		self._ensure_timeout = _EnsureTimeout(self)
		self.timeout_max = _TIMEOUT_MAX

	def ensure_timeout(self):
		return self._ensure_timeout

	def is_ipv6(self):
		return self.family == socket.AF_INET6

	def data_available(self, timeout=None):
		return select.select((self,), (), (), timeout or self.timeout_max)[0]


	def clear_buffer(self, timeout=1, *, esc_data=None):
		"""Clear input buffer of socket.

		Returns True if a timeout occurs,
			False if there is more data to read.

		The socket will send esc_data if defined before receiving data,
			e.g. esc_data=b'\n'.
		"""
		with self._ensure_timeout:
			t_end = time.monotonic() + self.timeout_max
			self.settimeout(timeout)
			try:
				while time.monotonic() < t_end:
					if esc_data:
						try:
							self.send(esc_data)
						except Timeout:
							esc_data = None
					if not self.recv(2**16):
						return True
			except Timeout:
				return True
			return False


	def accept(self):
		'''returns (tsocket.Socket, addr)'''
		(sock, addr) = super().accept()
		return self.__class__(sock, timeout=self.timeout), addr
	def taccept(self, timeout=_TIMEOUT_MID):
		'''same as accept, but also sets a different timeout'''
		(sock, addr) = super().accept()
		return self.__class__(sock, timeout=timeout), addr


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
				raise Timeout('tsend max-timeout, not sent: {} bytes'.format(tosend))

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
						raise Timeout('max-timeout')
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
				return b''
			size -= len(data)
			lst.append(data)
			if not size:
				return b''.join(lst)
			if t_end < time.monotonic():
				raise Timeout('max-timeout')

	def recv_until(self, maxlen=2**16, end_char=b'\n'):
		'''receives all bytes until end_char, not useable with udp'''
		t_end = time.monotonic() + self.timeout_max
		data = bytearray()
		for _ in range(maxlen):
			c = self.recv(1)
			if not c:
				return b''
			if c == end_char:
				return bytes(data)
			if t_end < time.monotonic():
				raise Timeout('max-timeout')
			data.extend(c)
		raise ValueError('end character not found within {} bytes'.format(len(data)))

	def get_addrlst(self, hostaddr):
		return get_ipv6_addrlst(hostaddr, self.is_ipv6())[1]

#-------------------------------------------------------

def is_ipv6_addr(addr):
	(fam, _, _, _, addr) = socket.getaddrinfo(addr[0], addr[1])[0]
	return fam == socket.AF_INET6, addr

def get_ipv6_addrlst(hostaddr, ipv6=None):
	lst = []
	af = None if ipv6 is None else socket.AF_INET6 if ipv6 else socket.AF_INET
	for (fam, _, _, _, addr) in socket.getaddrinfo(hostaddr[0], hostaddr[1]):
		if fam != af:
			if af is None and fam in (socket.AF_INET, socket.AF_INET6):
				af = fam
			elif ipv6 and fam == socket.AF_INET:
				addr = ('::ffff:'+addr[0], addr[1])
			else:
				continue
		elif ipv6:
			ipv6 = None
		if addr not in lst:
			lst.append(addr)
	if not lst:
		raise GAIError('no ip address found for {}'.format(hostaddr))
	return af == socket.AF_INET6, lst

def find_free_addr(*args, udp=False):
	'''first argument must be an address, followed by ports or more addresses'''
	ip = args[0][0]
	addrlst = (x if isinstance(x, tuple) else (ip, x) for x in args)
	for addr in addrlst:
		with Socket(ipv6=is_ipv6_addr(addr)[0] if addr[0] else USE_IPV6, udp=udp) as sock:
			try:
				if not addr[0] and USE_IPV6: setsockopt_ipv6only(sock, False)
				sock.bind(addr)
				return (addr[0], sock.getsockname()[1])
			except OSError:
				pass
	return None


def create_serversock(port, udp=False, reuseaddr=None):
	if USE_IPV6:
		sock = Socket(ipv6=True, udp=udp)
		setsockopt_ipv6only(sock, False)
	else:
		sock = Socket(ipv6=False, udp=udp)
	if reuseaddr is not None:
		setsockopt_reuseaddr(sock, reuseaddr)
	sock.bind(('', port))
	return sock

def create_connection(address, timeout=_TIMEOUT_MAX, source_address=None):
	sock = socket.create_connection(address, timeout, source_address)
	return Socket(sock, timeout=_TIMEOUT_MID)


def setsockopt_ipv6only(sock, v6only):
	sock.setsockopt(getattr(socket, 'IPPROTO_IPV6', 41), socket.IPV6_V6ONLY, 1 if v6only else 0)

def setsockopt_broadcast(sock, enable):
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1 if enable else 0)

def setsockopt_reuseaddr(sock, enable):
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 if enable else 0)
