"""Socket wrapper with simplified ipv6 and timeout support."""
__version__ = '0.2.23'

import select
import socket
import sys
import time
from collections.abc import Sequence
from typing import Any
Self = Any  # TODO: use typing.Self from 2026

_TIMEOUT_MAX = 30.0  # used for udp or waiting for messages
_TIMEOUT_TCP = 2.0  # timeout for connected tcp socket

HAS_IPV6 = socket.has_ipv6
Timeout = socket.timeout
GAIError = socket.gaierror

IpAddrType = tuple[str, int] | tuple[str, int, int, int]

#-------------------------------------------------------

class _EnsureTimeout:
	def __init__(self, sock: socket.socket):
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
	def __init__(self, sock: socket.socket|None = None, *,
			ipv6: bool = False, udp: bool = False, timeout: float|None = None):
		"""Create a (tcp) socket with timeout.

		If sock is already a socket a tsocket.Socket will be generated. The origin socket will be closed.
		"""
		if sock:
			super().__init__(sock.family, sock.type, sock.proto, fileno=sock.detach())
			super().settimeout(timeout or sock.gettimeout())
		else:
			super().__init__(socket.AF_INET6 if ipv6 else socket.AF_INET,
				socket.SOCK_DGRAM if udp else socket.SOCK_STREAM)
			super().settimeout(timeout or _TIMEOUT_MAX)
		self._ensure_timeout = _EnsureTimeout(self)
		self.maxtimeout = _TIMEOUT_MAX

	def is_ipv6(self) -> bool:
		return self.family == socket.AF_INET6

	def get_addrlst(self, hostaddr: IpAddrType) -> list[IpAddrType]:
		return get_ipv6_addrlst(hostaddr, self.is_ipv6())[1]

	def accept(self) -> tuple[Self, IpAddrType]:
		"""Return (tsocket.Socket, addr)."""
		(sock, addr) = super().accept()
		return self.__class__(sock, timeout=self.timeout), addr
	def taccept(self, timeout: float|None = _TIMEOUT_TCP) -> tuple[Self, IpAddrType]:
		"""Same as accept, but also sets a different timeout."""
		(sock, addr) = super().accept()
		return self.__class__(sock, timeout=timeout), addr

	def data_available(self, timeout: float|None = None):
		return select.select((self,), (), (), timeout or self.maxtimeout)[0]

	def ensure_timeout(self) -> _EnsureTimeout:
		return self._ensure_timeout


	def tsend(self, data: bytes) -> None:
		"""Send all data within maxtimeout."""
		t_max = time.monotonic() + self.maxtimeout
		tosend = len(data)
		while tosend:
			if tosend < 2**16:
				self.sendall(data[-tosend:])
				break
			tosend -= self.send(data[-tosend:])
			if t_max < time.monotonic():
				raise Timeout(f'tsend maxtimeout, not sent: {tosend} bytes')

	def send_list(self, lst: Sequence[bytes]) -> int:
		totalen = sum(map(len, lst))
		if totalen < 2**16:
			self.sendall(b''.join(lst))
		else:
			t_max = time.monotonic() + self.maxtimeout
			for data in lst:
				tosend = len(data)
				while tosend:
					if t_max < time.monotonic():
						raise Timeout('maxtimeout')
					if tosend < 2**16:
						self.sendall(data[-tosend:])
						break
					tosend -= self.send(data[-tosend:])
		return totalen

	def recv_exactly(self, size: int) -> bytes:
		t_max = time.monotonic() + self.maxtimeout
		lst = []
		while data := self.recv(size):
			lst.append(data)
			size -= len(data)
			if not size:
				return b''.join(lst)
			if t_max < time.monotonic():
				raise Timeout('maxtimeout')
		return b''

	def recv_until(self, maxlen: int = 2**16, end_char: bytes = b'\n') -> bytes:
		"""Receive all bytes until end_char, not usable with udp."""
		t_max = time.monotonic() + self.maxtimeout
		data = bytearray()
		for _ in range(maxlen):
			c = self.recv(1)
			if not c:
				return b''
			if c == end_char:
				return bytes(data)
			if t_max < time.monotonic():
				raise Timeout('maxtimeout')
			data.extend(c)
		raise ValueError(f'end character not found within {len(data)} bytes')

	def clear_buffer(self, timeout: float = 1.0, *, esc_data: bytes|None = None) -> bool:
		"""Clear input buffer of socket.

		Returns True if a timeout occurs,
			False if there is more data to read.

		The socket will send esc_data if defined before receiving data,
			e.g. esc_data=b'\n'.
		"""
		with self._ensure_timeout:
			t_max = time.monotonic() + self.maxtimeout
			self.settimeout(timeout)
			try:
				while time.monotonic() < t_max:
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

#-------------------------------------------------------

def sopt_ipv6only(sock, v6only: bool) -> None:
	sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1 if v6only else 0)

def sopt_reuseaddr(sock, enable: bool) -> None:
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 if enable else 0)

def sopt_broadcast(sock, enable: bool) -> None:
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1 if enable else 0)

def sopt_add_multicast(sock, ip: str) -> None:
	if sock.is_ipv6():
		sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP,
			socket.inet_pton(socket.AF_INET6, ip) + b'\x00'*4)
	else:
		sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
			socket.inet_pton(socket.AF_INET, ip) + b'\x00'*4)


def is_ipv6_addr(addr: IpAddrType) -> tuple[bool, IpAddrType]:
	(fam, _, _, _, addr) = socket.getaddrinfo(addr[0], addr[1])[0]
	return fam == socket.AF_INET6, addr

def find_free_addr(addr: IpAddrType, *addrs: IpAddrType|int, udp: bool = False) -> tuple[str, int]:
	"""Get a free ipv6 or ipv4 address.

	First argument must be an address (ip, port) tuple,
	followed by alternative ports or addresses.
	Port 0 always returs a free port.
	Set udp=True if no tcp port is needed.
	"""
	addrlst = [addr]
	addrlst.extend(x if isinstance(x, tuple) else (addr[0], x) for x in addrs)
	for addr in addrlst:
		ipv6 = is_ipv6_addr(addr)[0] if addr[0] else HAS_IPV6
		with Socket(ipv6=ipv6, udp=udp) as sock:
			try:
				if ipv6 and not addr[0]:
					sopt_ipv6only(sock, False)
				sock.bind(addr)
				return (addr[0], sock.getsockname()[1])
			except OSError:
				pass
	raise OSError("given addresses not accessible")

def get_ipv6_addrlst(hostaddr: IpAddrType, ipv6: bool|None = None) -> tuple[bool, list[IpAddrType]]:
	lst = []
	af = None if ipv6 is None else socket.AF_INET6 if ipv6 else socket.AF_INET
	for (fam, _, _, _, addr) in socket.getaddrinfo(hostaddr[0], hostaddr[1]):
		if fam != af:
			if af is None and fam in {socket.AF_INET, socket.AF_INET6}:
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
		raise GAIError(f'no ip address found for {hostaddr}')
	return af == socket.AF_INET6, lst

def broadcast_addrs(port: int, ipv6: bool = False) -> tuple[IpAddrType, ...]:
	"""Return broadcast addresses to a given port.

	ipv4: '255.255.255.255' and localhost as fallback
	ipv6: 'ff02::1', '::ffff:255.255.255.255' and localhost
	localhost fallback seems necessary in Linux if no network is reachable
	"""
	return (('ff02::1', port), ('::ffff:255.255.255.255', port), ('::1', port)) \
		if ipv6 else (('255.255.255.255', port), ('127.0.0.1', port))


def create_connection(hostaddr: tuple[str, int],
		timeout: float = _TIMEOUT_MAX, bindaddr: IpAddrType|None = None) -> Socket:
	"""Connect to a TCP address and return the socket."""
	sock = socket.create_connection(hostaddr, timeout, bindaddr)
	return Socket(sock, timeout=_TIMEOUT_TCP)

def create_serversock(addr: IpAddrType = ('', 0), *,
		ipv6: bool|None = None, udp: bool = False, reuseaddr: bool|None = None) -> Socket:
	"""Create socket binded to addr.

	If ipv6 is None the socket will listen on IPv4 and v6 if possible.
	On UDP broadcast support is enabled;
	TCP socket listen on new connections.
	"""
	if ipv6 is None:
		ipv6 = is_ipv6_addr(addr)[0] if addr[0] else HAS_IPV6
		sock = Socket(ipv6=ipv6, udp=udp)
		if ipv6:
			sopt_ipv6only(sock, False)
	else:
		sock = Socket(ipv6=ipv6, udp=udp)
	if reuseaddr is not None:
		sopt_reuseaddr(sock, reuseaddr)
	if udp:
		sopt_broadcast(sock, True)
	if sys.platform.startswith('win'):
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 0 if reuseaddr else 1)
		if udp and ipv6:
			sopt_add_multicast(sock, 'ff02::1')
	sock.bind(addr)
	if not udp:
		sock.listen()
	return sock
