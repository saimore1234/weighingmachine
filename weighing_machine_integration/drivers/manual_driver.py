"""Manual entry "driver" - no physical connection at all.

Used when Connection Type = Manual, or as the fallback path for
"Allow Manual Weight" on a Weighing Field Mapping. The value is supplied
by the caller (the user typed it into the Live Weighing page / a document
field) rather than read from any hardware.
"""

from __future__ import annotations

from weighing_machine_integration.drivers.base import BaseDriver, DriverError
from weighing_machine_integration.parsers.base import WeighingResult


class ManualDriver(BaseDriver):
	def __init__(self, profile, manual_value=None, manual_unit=None):
		super().__init__(profile)
		self.manual_value = manual_value
		self.manual_unit = manual_unit

	def connect(self) -> None:
		self._connected = True

	def disconnect(self) -> None:
		self._connected = False

	def read_raw(self) -> str:
		if self.manual_value is None:
			raise DriverError("No manual weight value was supplied")
		return str(self.manual_value)

	def get_weight(self) -> WeighingResult:
		raw = self.read_raw()
		try:
			weight = float(raw)
		except (TypeError, ValueError):
			raise DriverError(f"Manual weight value is not numeric: {raw!r}")
		return WeighingResult(
			weight=weight,
			unit=self.manual_unit or self.profile.get("default_uom"),
			stable=True,
			raw_response=raw,
		)

	def send_command(self, command: str) -> None:
		# Manual mode has nothing to send commands to; silently accepted.
		return
