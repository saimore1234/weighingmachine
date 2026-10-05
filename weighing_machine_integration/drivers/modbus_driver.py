"""Modbus TCP driver.

Reads a configured holding/input register pair and decodes it into a
weight using the configured byte/word order and scale factor. This is
necessarily generic - real Modbus weight indicators vary in register
layout, so Scale Factor/Offset/Byte Order/Word Order are all
admin-configurable per profile rather than assumed.
"""

from __future__ import annotations

from weighing_machine_integration.drivers.base import BaseDriver, DriverError
from weighing_machine_integration.parsers.base import WeighingResult

try:
	from pymodbus.client import ModbusTcpClient
except ImportError:  # pragma: no cover - exercised via mocks in tests
	ModbusTcpClient = None


def _combine_registers(registers, word_order: str) -> int:
	if len(registers) == 1:
		return registers[0]
	hi, lo = registers[0], registers[1]
	if word_order == "Little Endian":
		hi, lo = lo, hi
	return (hi << 16) | lo


class ModbusDriver(BaseDriver):
	def __init__(self, profile):
		super().__init__(profile)
		self._client = None

	def connect(self) -> None:
		if ModbusTcpClient is None:
			raise DriverError(
				"pymodbus is not installed on the server. Install it with: pip install pymodbus"
			)

		host = self.profile.get("modbus_host")
		port = int(self.profile.get("modbus_port") or 502)
		if not host:
			raise DriverError("No Host configured on this machine profile")

		self._client = ModbusTcpClient(host, port=port)
		if not self._client.connect():
			raise DriverError(f"Could not connect to Modbus device at {host}:{port}")
		self._connected = True

	def disconnect(self) -> None:
		if self._client is not None:
			try:
				self._client.close()
			except Exception:
				pass
		self._client = None
		self._connected = False

	def read_raw(self) -> str:
		if not self._connected or self._client is None:
			raise DriverError("Not connected to Modbus device")

		address = self.profile.get("modbus_register")
		if address is None:
			raise DriverError("No Register configured on this machine profile")

		slave_id = int(self.profile.get("modbus_slave_id") or 1)
		register_type = self.profile.get("modbus_register_type") or "Holding Register"
		read_fn = (
			self._client.read_input_registers
			if register_type == "Input Register"
			else self._client.read_holding_registers
		)

		try:
			try:
				result = read_fn(address=int(address), count=2, slave=slave_id)
			except TypeError:
				# Older pymodbus releases use `unit=` instead of `slave=`.
				result = read_fn(address=int(address), count=2, unit=slave_id)
		except Exception as e:
			raise DriverError(f"Error reading Modbus register {address}: {e}")

		if result is None or result.isError():
			raise DriverError(f"Modbus read error on register {address}: {result}")

		return ",".join(str(r) for r in result.registers)

	def parse(self, raw_response: str):
		registers = [int(x) for x in raw_response.split(",") if x != ""]
		if not registers:
			raise DriverError("No registers returned from Modbus device")

		raw_value = _combine_registers(registers, self.profile.get("modbus_word_order") or "Big Endian")
		scale = float(self.profile.get("modbus_scale_factor") or 1)
		offset = float(self.profile.get("modbus_offset") or 0)
		weight = round(raw_value * scale + offset, int(self.profile.get("decimal_precision") or 2))

		if weight < 0 and not self.profile.get("negative_weight_allowed"):
			weight = abs(weight)

		return WeighingResult(weight=weight, unit=self.profile.get("default_uom"), raw_response=raw_response)

	def send_command(self, command: str) -> None:
		raise DriverError("Modbus TCP does not support free-form wire commands")
