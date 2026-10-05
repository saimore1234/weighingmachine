"""TCP/IP driver for network-attached weighing indicators."""

from __future__ import annotations

import socket

from weighing_machine_integration.drivers.base import BaseDriver, DriverError


def _unescape(value: str) -> str:
	if not value:
		return ""
	return value.encode("utf-8").decode("unicode_escape")


class TCPDriver(BaseDriver):
	def __init__(self, profile):
		super().__init__(profile)
		self._sock = None

	def connect(self) -> None:
		host = self.profile.get("tcp_host")
		port = self.profile.get("tcp_port")
		if not host or not port:
			raise DriverError("Host/Port not configured on this machine profile")

		timeout = float(self.profile.get("tcp_socket_timeout") or 5)
		try:
			self._sock = socket.create_connection((host, int(port)), timeout=timeout)
			self._connected = True
		except socket.timeout:
			raise DriverError(f"Connection to {host}:{port} timed out")
		except ConnectionRefusedError:
			raise DriverError(f"Connection to {host}:{port} was refused")
		except OSError as e:
			raise DriverError(f"Could not connect to {host}:{port}: {e}")

	def disconnect(self) -> None:
		if self._sock is not None:
			try:
				self._sock.close()
			except Exception:
				pass
		self._sock = None
		self._connected = False

	def read_raw(self) -> str:
		if not self._connected or self._sock is None:
			raise DriverError("Not connected to TCP machine")

		command = self.profile.get("read_command")
		if command:
			self.send_command(command)

		encoding = self.profile.get("tcp_encoding") or "ascii"
		terminator = _unescape(self.profile.get("tcp_terminator") or "\r\n").encode(encoding, errors="ignore")

		try:
			buffer = b""
			self._sock.settimeout(float(self.profile.get("tcp_socket_timeout") or 5))
			while terminator not in buffer:
				chunk = self._sock.recv(1024)
				if not chunk:
					break
				buffer += chunk
			if not buffer:
				raise DriverError("No data received from TCP machine")
			return buffer.decode(encoding, errors="replace").strip()
		except socket.timeout:
			raise DriverError("Timed out waiting for a response from the TCP machine")
		except DriverError:
			raise
		except OSError as e:
			raise DriverError(f"Error reading from TCP machine: {e}")

	def send_command(self, command: str) -> None:
		if not self._connected or self._sock is None:
			raise DriverError("Not connected to TCP machine")
		encoding = self.profile.get("tcp_encoding") or "ascii"
		terminator = _unescape(self.profile.get("command_terminator") or "\r\n")
		try:
			self._sock.sendall((command + terminator).encode(encoding, errors="ignore"))
		except OSError as e:
			raise DriverError(f"Error writing to TCP machine: {e}")
