"""End-to-end test against the live simulator processes (TCP plain on
19001, TCP delimited on 19002, HTTP JSON on 19003) - exercises the real
TCPDriver/HTTPDriver + parser engine, no mocks."""

from weighing_machine_integration.drivers.tcp_driver import TCPDriver
from weighing_machine_integration.drivers.http_driver import HTTPDriver


def execute():
	# --- TCP, Plain Numeric ---
	profile = {
		"connection_type": "TCP/IP",
		"tcp_host": "127.0.0.1", "tcp_port": 19001,
		"tcp_socket_timeout": 5, "tcp_encoding": "ascii", "tcp_terminator": "\r\n",
		"response_format": "Plain Numeric", "decimal_precision": 2,
	}
	driver = TCPDriver(profile)
	driver.connect()
	try:
		result = driver.get_weight()
		print("TCP plain:", result)
		assert result.weight is not None and result.weight > 0
		assert result.unit == "KG"
	finally:
		driver.disconnect()

	# --- TCP, Delimited Gross/Tare/Net ---
	profile2 = {
		"connection_type": "TCP/IP",
		"tcp_host": "127.0.0.1", "tcp_port": 19002,
		"tcp_socket_timeout": 5, "tcp_encoding": "ascii", "tcp_terminator": "\r\n",
		"response_format": "Delimited Gross/Tare/Net",
		"gross_weight_regex": r"GW=([\d.]+)", "tare_weight_regex": r"TW=([\d.]+)", "net_weight_regex": r"NW=([\d.]+)",
		"decimal_precision": 2,
	}
	driver2 = TCPDriver(profile2)
	driver2.connect()
	try:
		result2 = driver2.get_weight()
		print("TCP delimited:", result2)
		assert result2.gross_weight is not None and result2.tare_weight is not None and result2.net_weight is not None
		assert round(result2.gross_weight - result2.tare_weight, 2) == round(result2.net_weight, 2)
	finally:
		driver2.disconnect()

	# --- HTTP, JSON ---
	profile3 = {
		"connection_type": "HTTP API",
		"http_url": "http://127.0.0.1:19003/scale", "http_method": "GET", "http_timeout": 5,
		"response_format": "JSON Path",
		"weight_json_path": "data.weight", "unit_json_path": "data.unit", "stable_json_path": "data.stable",
		"decimal_precision": 2,
	}
	driver3 = HTTPDriver(profile3)
	driver3.connect()
	try:
		result3 = driver3.get_weight()
		print("HTTP json:", result3)
		assert result3.weight is not None
		assert result3.unit == "KG"
	finally:
		driver3.disconnect()

	print("END-TO-END SIMULATOR TEST: ALL PASSED")
