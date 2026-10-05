"""Stable-weight detection.

Pure function over a list of already-taken readings, so it's trivially
testable without any hardware/driver involved.
"""

from __future__ import annotations

from typing import Sequence


def is_stable(weights: Sequence[float], tolerance: float = 0.02) -> bool:
	"""True if every reading is within `tolerance` of every other reading."""
	if not weights:
		return False
	if len(weights) == 1:
		return True
	return (max(weights) - min(weights)) <= tolerance


def take_stable_reading(driver, minimum_stable_readings: int = 3, tolerance: float = 0.02, max_attempts: int = 10):
	"""Repeatedly reads from `driver` until `minimum_stable_readings`
	consecutive readings agree within `tolerance`, or `max_attempts` is hit.

	Returns (result, stable: bool) where `result` is the last WeighingResult
	taken. Never raises for "didn't stabilise" - that's communicated via the
	returned stable flag so callers can decide (e.g. Weighing Reading
	status = Unstable rather than a hard failure).
	"""
	minimum_stable_readings = max(1, int(minimum_stable_readings or 1))
	window = []
	last_result = None

	for _ in range(max(max_attempts, minimum_stable_readings)):
		last_result = driver.get_weight()
		value = last_result.resolve_weight()
		if value is None:
			continue

		window.append(value)
		window = window[-minimum_stable_readings:]

		if len(window) == minimum_stable_readings and is_stable(window, tolerance):
			last_result.stable = True
			return last_result, True

	if last_result is not None:
		last_result.stable = False
	return last_result, False
