import unittest

from weighing_machine_integration.parsers.base import ParseError
from weighing_machine_integration.parsers.engine import parse_response


class TestPlainNumericParser(unittest.TestCase):
	def test_basic(self):
		r = parse_response("1250.50", {"response_format": "Plain Numeric", "decimal_precision": 2})
		self.assertEqual(r.weight, 1250.5)

	def test_with_unit_suffix(self):
		r = parse_response("+001250.50 KG", {"response_format": "Plain Numeric", "decimal_precision": 2})
		self.assertEqual(r.weight, 1250.5)
		self.assertEqual(r.unit, "KG")

	def test_minimal_format(self):
		r = parse_response("W:1250.50", {"response_format": "Plain Numeric", "decimal_precision": 2})
		self.assertEqual(r.weight, 1250.5)

	def test_negative_disallowed_by_default(self):
		r = parse_response("-5.00", {"response_format": "Plain Numeric", "decimal_precision": 2})
		self.assertEqual(r.weight, 5.0)

	def test_negative_allowed_when_configured(self):
		r = parse_response("-5.00", {"response_format": "Plain Numeric", "decimal_precision": 2,
										"negative_weight_allowed": 1})
		self.assertEqual(r.weight, -5.0)

	def test_empty_response_raises(self):
		with self.assertRaises(ParseError):
			parse_response("", {"response_format": "Plain Numeric"})

	def test_no_number_raises(self):
		with self.assertRaises(ParseError):
			parse_response("ERROR NO SCALE", {"response_format": "Plain Numeric"})

	def test_custom_decimal_separator(self):
		r = parse_response("1250,50 kg", {"response_format": "Plain Numeric",
											"decimal_separator": ",", "decimal_precision": 2})
		self.assertEqual(r.weight, 1250.5)


class TestRegexParser(unittest.TestCase):
	def test_weight_regex(self):
		r = parse_response("ST,GS,001250.50kg", {
			"response_format": "Regex",
			"weight_regex": r"GS,(\d+\.\d+)",
			"decimal_precision": 2,
		})
		self.assertEqual(r.weight, 1250.5)

	def test_gross_tare_net(self):
		r = parse_response("GW=1250.50,TW=10.00,NW=1240.50", {
			"response_format": "Delimited Gross/Tare/Net",
			"gross_weight_regex": r"GW=([\d.]+)",
			"tare_weight_regex": r"TW=([\d.]+)",
			"net_weight_regex": r"NW=([\d.]+)",
			"decimal_precision": 2,
		})
		self.assertEqual(r.gross_weight, 1250.5)
		self.assertEqual(r.tare_weight, 10.0)
		self.assertEqual(r.net_weight, 1240.5)
		self.assertEqual(r.weight, 1240.5)  # falls back to net

	def test_stable_regex_with_value(self):
		r = parse_response("ST,1250.50,kg", {
			"response_format": "Regex",
			"weight_regex": r",(\d+\.\d+),",
			"stable_regex": r"^(ST|US)",
			"stable_value": "ST",
			"decimal_precision": 2,
		})
		self.assertTrue(r.stable)

	def test_unstable_regex_with_value(self):
		r = parse_response("US,1250.50,kg", {
			"response_format": "Regex",
			"weight_regex": r",(\d+\.\d+),",
			"stable_regex": r"^(ST|US)",
			"stable_value": "ST",
			"decimal_precision": 2,
		})
		self.assertFalse(r.stable)

	def test_no_match_raises(self):
		with self.assertRaises(ParseError):
			parse_response("garbage", {"response_format": "Regex", "weight_regex": r"GS,(\d+\.\d+)"})

	def test_invalid_regex_raises(self):
		with self.assertRaises(ParseError):
			parse_response("1.00", {"response_format": "Regex", "weight_regex": r"("})


class TestJSONPathParser(unittest.TestCase):
	def test_basic_path(self):
		r = parse_response(
			'{"data": {"weight": 1250.50, "unit": "kg", "stable": true}}',
			{"response_format": "JSON Path", "weight_json_path": "data.weight",
			 "unit_json_path": "data.unit", "stable_json_path": "data.stable"},
		)
		self.assertEqual(r.weight, 1250.5)
		self.assertEqual(r.unit, "KG")
		self.assertTrue(r.stable)

	def test_array_index_path(self):
		r = parse_response(
			'{"items": [{"weight": 42.5}]}',
			{"response_format": "JSON Path", "weight_json_path": "items[0].weight"},
		)
		self.assertEqual(r.weight, 42.5)

	def test_invalid_json_raises(self):
		with self.assertRaises(ParseError):
			parse_response("{not json", {"response_format": "JSON Path", "weight_json_path": "data.weight"})

	def test_missing_path_raises(self):
		with self.assertRaises(ParseError):
			parse_response('{"data": {}}', {"response_format": "JSON Path", "weight_json_path": "data.missing"})

	def test_gross_tare_net_json(self):
		r = parse_response(
			'{"gw": 100.0, "tw": 10.0}',
			{"response_format": "JSON Path", "gross_json_path": "gw", "tare_json_path": "tw"},
		)
		self.assertEqual(r.gross_weight, 100.0)
		self.assertEqual(r.tare_weight, 10.0)
		self.assertEqual(r.net_weight, 90.0)  # derived
