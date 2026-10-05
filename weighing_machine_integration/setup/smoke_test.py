"""Quick import/sanity smoke test - not the real test suite (see tests/)."""

import frappe


def execute():
	from weighing_machine_integration.drivers.registry import create_driver, get_driver_class
	from weighing_machine_integration.parsers.engine import parse_response
	from weighing_machine_integration.services import conversion_service, machine_service, mapping_service, stability_service

	print("All core modules imported OK")

	# Plain numeric parse
	r = parse_response("+001250.50 KG", {"response_format": "Plain Numeric", "decimal_precision": 2})
	assert r.weight == 1250.5, r.weight
	assert r.unit == "KG", r.unit

	# Regex gross/tare/net parse
	r2 = parse_response(
		"GW=1250.50,TW=10.00,NW=1240.50",
		{
			"response_format": "Delimited Gross/Tare/Net",
			"gross_weight_regex": r"GW=([\d.]+)",
			"tare_weight_regex": r"TW=([\d.]+)",
			"net_weight_regex": r"NW=([\d.]+)",
			"decimal_precision": 2,
		},
	)
	assert r2.gross_weight == 1250.5 and r2.tare_weight == 10.0 and r2.net_weight == 1240.5, r2

	# JSON path parse
	r3 = parse_response(
		'{"data": {"weight": 1250.5, "unit": "kg", "stable": true}}',
		{"response_format": "JSON Path", "weight_json_path": "data.weight", "unit_json_path": "data.unit",
		 "stable_json_path": "data.stable", "decimal_precision": 2},
	)
	assert r3.weight == 1250.5 and r3.stable is True and r3.unit == "KG", r3

	# Conversion
	assert conversion_service.convert(1, "TON", "KG") == 1000
	assert round(conversion_service.convert(1000, "G", "KG"), 3) == 1.0

	# Driver registry
	assert get_driver_class("Manual").__name__ == "ManualDriver"

	print("All smoke assertions passed")
