import unittest

from weighing_machine_integration.parsers.base import WeighingResult
from weighing_machine_integration.services.stability_service import is_stable, take_stable_reading


class FakeDriver:
	"""Returns a pre-set sequence of weights, one per get_weight() call."""

	def __init__(self, weights):
		self._weights = list(weights)

	def get_weight(self):
		value = self._weights.pop(0) if self._weights else self._weights[-1]
		return WeighingResult(weight=value, raw_response=str(value))


class TestIsStable(unittest.TestCase):
	def test_single_reading_is_stable(self):
		self.assertTrue(is_stable([100.0]))

	def test_within_tolerance(self):
		self.assertTrue(is_stable([100.0, 100.1, 100.19], tolerance=0.2))

	def test_outside_tolerance(self):
		self.assertFalse(is_stable([100.0, 101.0, 100.0], tolerance=0.2))

	def test_empty_is_not_stable(self):
		self.assertFalse(is_stable([]))


class TestTakeStableReading(unittest.TestCase):
	def test_settles_within_attempts(self):
		driver = FakeDriver([105.0, 98.0, 100.0, 100.0, 100.0, 100.0])
		result, stable = take_stable_reading(driver, minimum_stable_readings=3, tolerance=0.01, max_attempts=10)
		self.assertTrue(stable)
		self.assertEqual(result.weight, 100.0)

	def test_never_settles_returns_unstable(self):
		driver = FakeDriver([100.0, 150.0, 90.0, 140.0, 95.0, 145.0, 92.0, 148.0])
		result, stable = take_stable_reading(driver, minimum_stable_readings=3, tolerance=0.01, max_attempts=8)
		self.assertFalse(stable)
		self.assertIsNotNone(result)

	def test_single_reading_requirement(self):
		driver = FakeDriver([42.0])
		result, stable = take_stable_reading(driver, minimum_stable_readings=1, tolerance=0.01, max_attempts=3)
		self.assertTrue(stable)
		self.assertEqual(result.weight, 42.0)
