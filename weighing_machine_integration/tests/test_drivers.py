"""Driver tests, all with hardware mocked out - no physical machine
required, matching the project's "never requires hardware" test rule."""

import unittest
from unittest.mock import MagicMock, patch

from weighing_machine_integration.drivers.base import DriverError
from weighing_machine_integration.drivers.http_driver import HTTPDriver
from weighing_machine_integration.drivers.manual_driver import ManualDriver
from weighing_machine_integration.drivers.registry import create_driver, get_driver_class
from weighing_machine_integration.drivers.serial_driver import SerialDriver
from weighing_machine_integration.drivers.tcp_driver import TCPDriver


class TestManualDriver(unittest.TestCase):
	def test_returns_supplied_value(self):
		driver = ManualDriver({"default_uom": "KG"}, manual_value=55.5)
		driver.connect()
		result = driver.get_weight()
		self.assertEqual(result.weight, 55.5)
		self.assertTrue(result.stable)

	def test_no_value_raises(self):
		driver = ManualDriver({"default_uom": "KG"})
		driver.connect()
		with self.assertRaises(DriverError):
			driver.get_weight()

	def test_non_numeric_value_raises(self):
		driver = ManualDriver({"default_uom": "KG"}, manual_value="not-a-number")
		driver.connect()
		with self.assertRaises(DriverError):
			driver.get_weight()


class TestSerialDriver(unittest.TestCase):
	@patch("weighing_machine_integration.drivers.serial_driver.pyserial")
	def test_connect_read_disconnect(self, mock_pyserial):
		mock_conn = MagicMock()
		mock_conn.read_until.return_value = b"1250.50 kg\r\n"
		mock_pyserial.Serial.return_value = mock_conn

		profile = {
			"serial_port": "COM3", "baud_rate": "9600", "data_bits": "8", "stop_bits": "1",
			"parity": "None", "serial_read_timeout": 2, "serial_write_timeout": 2,
			"serial_encoding": "ascii", "serial_line_terminator": "\\r\\n",
			"response_format": "Plain Numeric", "decimal_precision": 2,
		}
		driver = SerialDriver(profile)
		driver.connect()
		self.assertTrue(driver.is_connected())

		result = driver.get_weight()
		self.assertEqual(result.weight, 1250.5)

		driver.disconnect()
		mock_conn.close.assert_called_once()

	def test_missing_port_raises(self):
		with patch("weighing_machine_integration.drivers.serial_driver.pyserial") as mock_pyserial:
			mock_pyserial.Serial = MagicMock()
			driver = SerialDriver({"response_format": "Plain Numeric"})
			with self.assertRaises(DriverError):
				driver.connect()

	def test_missing_dependency_raises_clear_error(self):
		with patch("weighing_machine_integration.drivers.serial_driver.pyserial", None):
			driver = SerialDriver({"serial_port": "COM3"})
			with self.assertRaises(DriverError):
				driver.connect()


class TestTCPDriver(unittest.TestCase):
	@patch("weighing_machine_integration.drivers.tcp_driver.socket.create_connection")
	def test_connect_read_disconnect(self, mock_create_conn):
		mock_sock = MagicMock()
		mock_sock.recv.side_effect = [b"1250.50 kg\r\n", b""]
		mock_create_conn.return_value = mock_sock

		profile = {
			"tcp_host": "10.0.0.5", "tcp_port": 2000, "tcp_socket_timeout": 5,
			"tcp_encoding": "ascii", "tcp_terminator": "\\r\\n",
			"response_format": "Plain Numeric", "decimal_precision": 2,
		}
		driver = TCPDriver(profile)
		driver.connect()
		result = driver.get_weight()
		self.assertEqual(result.weight, 1250.5)
		driver.disconnect()
		mock_sock.close.assert_called_once()

	@patch("weighing_machine_integration.drivers.tcp_driver.socket.create_connection")
	def test_connection_refused_raises_driver_error(self, mock_create_conn):
		mock_create_conn.side_effect = ConnectionRefusedError()
		driver = TCPDriver({"tcp_host": "10.0.0.5", "tcp_port": 2000})
		with self.assertRaises(DriverError):
			driver.connect()

	def test_missing_host_raises(self):
		driver = TCPDriver({"tcp_port": 2000})
		with self.assertRaises(DriverError):
			driver.connect()


class TestHTTPDriver(unittest.TestCase):
	@patch("weighing_machine_integration.drivers.http_driver.requests.request")
	def test_json_response(self, mock_request):
		mock_response = MagicMock(status_code=200, text='{"weight": 10}')
		mock_request.return_value = mock_response

		profile = {
			"http_url": "http://scale.local/read", "http_method": "GET", "http_timeout": 5,
			"response_format": "JSON Path", "weight_json_path": "weight", "decimal_precision": 2,
		}
		driver = HTTPDriver(profile)
		driver.connect()
		result = driver.get_weight()
		self.assertEqual(result.weight, 10)

	@patch("weighing_machine_integration.drivers.http_driver.requests.request")
	def test_auth_failure_raises(self, mock_request):
		mock_request.return_value = MagicMock(status_code=401, text="Unauthorized")
		driver = HTTPDriver({"http_url": "http://scale.local/read", "http_method": "GET"})
		driver.connect()
		with self.assertRaises(DriverError):
			driver.read_raw()

	def test_missing_url_raises(self):
		driver = HTTPDriver({})
		with self.assertRaises(DriverError):
			driver.connect()


class TestDriverRegistry(unittest.TestCase):
	def test_all_connection_types_resolve(self):
		for connection_type in ("Serial", "TCP/IP", "HTTP API", "Modbus TCP", "Manual"):
			self.assertIsNotNone(get_driver_class(connection_type))

	def test_unknown_connection_type_raises(self):
		with self.assertRaises(DriverError):
			get_driver_class("Carrier Pigeon")

	def test_create_driver_dispatches(self):
		driver = create_driver({"connection_type": "Manual"}, manual_value=1)
		self.assertIsInstance(driver, ManualDriver)
