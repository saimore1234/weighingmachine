"""RS232/USB-Serial driver. All settings come from the Weighing Machine
Profile - nothing is hardcoded here.
"""

from __future__ import annotations

from weighing_machine_integration.drivers.base import BaseDriver, DriverError

try:
	import serial as pyserial
except ImportError:  # pragma: no cover - exercised via mocks in tests
	pyserial = None

_PARITY_MAP = {"None": "N", "Even": "E", "Odd": "O", "Mark": "M", "Space": "S"}
_STOPBITS_MAP = {"1": 1, "1.5": 1.5, "2": 2}


def _unescape(value: str) -> str:
	"""Turn a UI-entered "\\r\\n" into an actual CR LF."""
	if not value:
		return ""
	return value.encode("utf-8").decode("unicode_escape")


class SerialDriver(BaseDriver):
	def __init__(self, profile):
		super().__init__(profile)
		self._conn = None

	def connect(self) -> None:
		if pyserial is None:
			raise DriverError(
				"pyserial is not installed on the server. Install it with: pip install pyserial"
			)

		port = self.profile.get("serial_port")
		if not port:
			raise DriverError("No Port configured on this machine profile")

		try:
			self._conn = pyserial.Serial(
				port=port,
				baudrate=int(self.profile.get("baud_rate") or 9600),
				bytesize=int(self.profile.get("data_bits") or 8),
				stopbits=_STOPBITS_MAP.get(str(self.profile.get("stop_bits") or "1"), 1),
				parity=_PARITY_MAP.get(self.profile.get("parity") or "None", "N"),
				timeout=float(self.profile.get("serial_read_timeout") or 2),
				write_timeout=float(self.profile.get("serial_write_timeout") or 2),
			)
			self._connected = True
		except Exception as e:
			raise DriverError(f"Could not open serial port {port}: {e}")

	def disconnect(self) -> None:
		if self._conn is not None:
			try:
				self._conn.close()
			except Exception:
				pass
		self._conn = None
		self._connected = False

	def read_raw(self) -> str:
		if not self._connected or self._conn is None:
			raise DriverError("Not connected to serial machine")

		command = self.profile.get("read_command")
		if command:
			self.send_command(command)

		try:
			terminator = _unescape(self.profile.get("serial_line_terminator") or "\r\n")
			encoding = self.profile.get("serial_encoding") or "ascii"
			if terminator:
				raw_bytes = self._conn.read_until(terminator.encode(encoding, errors="ignore"))
			else:
				raw_bytes = self._conn.readline()
			if not raw_bytes:
				raise DriverError("Timed out waiting for a response from the machine")
			return raw_bytes.decode(encoding, errors="replace").strip()
		except DriverError:
			raise
		except Exception as e:
			raise DriverError(f"Error reading from serial machine: {e}")

	def send_command(self, command: str) -> None:
		if not self._connected or self._conn is None:
			raise DriverError("Not connected to serial machine")
		terminator = _unescape(self.profile.get("command_terminator") or "\r\n")
		encoding = self.profile.get("serial_encoding") or "ascii"
		try:
			self._conn.write((command + terminator).encode(encoding, errors="ignore"))
		except Exception as e:
			raise DriverError(f"Error writing to serial machine: {e}")
