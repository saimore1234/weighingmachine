"""Parses a bare numeric response, optionally followed by a unit.

Handles things like:
	"1250.50"
	"1250.50 kg"
	"+001250.50 KG"
"""

from __future__ import annotations

import re

from weighing_machine_integration.parsers.base import ParseError, WeighingResult
from weighing_machine_integration.utils.validation import clamp_precision, to_float

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_UNIT_RE = re.compile(r"[A-Za-z]+")


def parse(raw_response: str, profile) -> WeighingResult:
	if not raw_response or not raw_response.strip():
		raise ParseError("Empty response from machine")

	match = _NUMBER_RE.search(raw_response)
	if not match:
		raise ParseError(f"No numeric weight found in response: {raw_response!r}")

	weight = to_float(
		match.group(0),
		decimal_separator=profile.get("decimal_separator") or ".",
		thousands_separator=profile.get("thousands_separator") or "",
	)
	if weight is None:
		raise ParseError(f"Could not parse numeric weight from: {match.group(0)!r}")

	if not profile.get("negative_weight_allowed") and weight < 0:
		weight = abs(weight)

	weight = clamp_precision(weight, profile.get("decimal_precision") or 2)

	unit_match = _UNIT_RE.search(raw_response[match.end():])
	unit = unit_match.group(0).upper() if unit_match else None

	return WeighingResult(weight=weight, unit=unit, raw_response=raw_response)
