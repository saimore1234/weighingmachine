import unittest

from weighing_machine_integration.services.conversion_service import convert, to_kg


class TestConversionService(unittest.TestCase):
	def test_identity(self):
		self.assertEqual(convert(100, "KG", "KG"), 100)

	def test_ton_to_kg(self):
		self.assertEqual(convert(1, "TON", "KG"), 1000)

	def test_g_to_kg(self):
		self.assertAlmostEqual(convert(1000, "G", "KG"), 1.0)

	def test_lb_to_kg(self):
		self.assertAlmostEqual(convert(1, "LB", "KG"), 0.45359237)

	def test_kg_to_lb(self):
		self.assertAlmostEqual(convert(1, "KG", "LB"), 1 / 0.45359237)

	def test_round_trip(self):
		value = 123.456
		converted = convert(convert(value, "KG", "LB"), "LB", "KG")
		self.assertAlmostEqual(converted, value, places=6)

	def test_none_passthrough(self):
		self.assertIsNone(convert(None, "KG", "LB"))

	def test_unknown_unit_raises(self):
		with self.assertRaises(ValueError):
			convert(1, "FURLONG", "KG")

	def test_to_kg_default_unit(self):
		self.assertEqual(to_kg(5, None), 5)
