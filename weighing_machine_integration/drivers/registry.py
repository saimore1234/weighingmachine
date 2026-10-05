"""Factory: Connection Type (a plain string from the Profile doctype) ->
driver class. This is the only place that maps a connection type name to
code - adding a new transport means adding one line here and one driver
module, nothing else in the app needs to change.
"""

from __future__ import annotations

from weighing_machine_integration.drivers.base import DriverError
from weighing_machine_integration.drivers.http_driver import HTTPDriver
from weighing_machine_integration.drivers.manual_driver import ManualDriver
from weighing_machine_integration.drivers.modbus_driver import ModbusDriver
from weighing_machine_integration.drivers.serial_driver import SerialDriver
from weighing_machine_integration.drivers.tcp_driver import TCPDriver

_REGISTRY = {
	"Serial": SerialDriver,
	"TCP/IP": TCPDriver,
	"HTTP API": HTTPDriver,
	"Modbus TCP": ModbusDriver,
	"Manual": ManualDriver,
}


def get_driver_class(connection_type: str):
	driver_class = _REGISTRY.get(connection_type)
	if not driver_class:
		raise DriverError(f"Unsupported connection type: {connection_type!r}")
	return driver_class


def create_driver(profile, **kwargs):
	"""profile: Weighing Machine Profile document (or dict-like with
	.get("connection_type"))."""
	driver_class = get_driver_class(profile.get("connection_type"))
	return driver_class(profile, **kwargs) if driver_class is ManualDriver else driver_class(profile)
