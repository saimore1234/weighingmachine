"""Universal driver interface.

Every driver (Serial/TCP/HTTP/Modbus/Manual) implements this contract and
takes ALL of its configuration from a Weighing Machine Profile document -
never from hardcoded values. Drivers never raise for expected/operational
failures (disconnected, timeout, refused, ...); they raise DriverError with
a clear message, which calling code converts into a Weighing Machine Log
entry and a user-facing message instead of crashing anything.
"""

from __future__ import annotations

from weighing_machine_integration.parsers.engine import parse_response
from weighing_machine_integration.parsers.base import WeighingResult


class DriverError(Exception):
	"""Raised for any connection/read/write failure a driver encounters."""


class BaseDriver:
	def __init__(self, profile):
		"""profile: a Weighing Machine Profile document (or dict-like)."""
		self.profile = profile
		self._connected = False

	# ------------------------------------------------------------
	# Lifecycle - concrete drivers must implement these
	# ------------------------------------------------------------

	def connect(self) -> None:
		raise NotImplementedError

	def disconnect(self) -> None:
		raise NotImplementedError

	def is_connected(self) -> bool:
		return self._connected

	def read_raw(self) -> str:
		"""Return the raw response text/bytes-as-text from the machine."""
		raise NotImplementedError

	# ------------------------------------------------------------
	# Shared behaviour - parsing, zero/tare are generic once read_raw()
	# and a command-sender exist.
	# ------------------------------------------------------------

	def parse(self, raw_response: str) -> WeighingResult:
		return parse_response(raw_response, self.profile)

	def get_weight(self) -> WeighingResult:
		raw = self.read_raw()
		return self.parse(raw)

	def send_command(self, command: str) -> None:
		"""Override in drivers that support sending commands (Serial/TCP)."""
		raise NotImplementedError(f"{self.__class__.__name__} does not support sending commands")

	def zero(self) -> None:
		command = (self.profile.get("zero_command") or "").strip()
		if not command:
			raise DriverError("No Zero Command configured on this machine profile")
		self.send_command(command)

	def tare(self) -> None:
		command = (self.profile.get("tare_command") or "").strip()
		if not command:
			raise DriverError("No Tare Command configured on this machine profile")
		self.send_command(command)

	def test_connection(self) -> dict:
		"""Connect, read once, disconnect. Returns a diagnostic dict - never
		raises; errors are reported in the returned dict so the UI can show
		them cleanly.
		"""
		import time

		started = time.monotonic()
		was_connected_before = self.is_connected()
		try:
			if not was_connected_before:
				self.connect()
			raw = self.read_raw()
			result = self.parse(raw)
			return {
				"success": True,
				"raw_response": raw,
				"weight": result.weight,
				"unit": result.unit,
				"stable": result.stable,
				"elapsed_seconds": round(time.monotonic() - started, 3),
			}
		except Exception as e:
			return {
				"success": False,
				"error": str(e),
				"elapsed_seconds": round(time.monotonic() - started, 3),
			}
		finally:
			if not was_connected_before:
				try:
					self.disconnect()
				except Exception:
					pass

	def __enter__(self):
		self.connect()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		try:
			self.disconnect()
		except Exception:
			pass
