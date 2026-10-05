"""Configuration-driven regex parser.

Every field (weight / gross / tare / net / unit / stable) is optional and
independently configured on the Weighing Machine Profile. Handles both the
"Regex" (single weight_regex) and "Delimited Gross/Tare/Net" response
formats - they're the same mechanism, just configured differently.

Examples this covers:
	"ST,GS,001250.50kg"                      -> weight_regex
	"GW=1250.50,TW=10.00,NW=1240.50"         -> gross/tare/net regex
"""

from __future__ import annotations

import re

from weighing_machine_integration.parsers.base import ParseError, WeighingResult
from weighing_machine_integration.utils.validation import clamp_precision, to_float


def _extract(raw_response: str, pattern: str):
	if not pattern:
		return None
	try:
		match = re.search(pattern, raw_response)
	except re.error as e:
		raise ParseError(f"Invalid regex {pattern!r}: {e}")
	if not match:
		return None
	# Use the first capture group if the pattern defines one, else the full match.
	return match.group(1) if match.groups() else match.group(0)


def parse(raw_response: str, profile) -> WeighingResult:
	if not raw_response or not raw_response.strip():
		raise ParseError("Empty response from machine")

	precision = profile.get("decimal_precision") or 2
	dec_sep = profile.get("decimal_separator") or "."
	thou_sep = profile.get("thousands_separator") or ""

	def num(pattern):
		raw = _extract(raw_response, pattern)
		return clamp_precision(to_float(raw, dec_sep, thou_sep), precision) if raw is not None else None

	weight = num(profile.get("weight_regex"))
	gross = num(profile.get("gross_weight_regex"))
	tare = num(profile.get("tare_weight_regex"))
	net = num(profile.get("net_weight_regex"))

	if weight is None and net is None and gross is None:
		raise ParseError(f"None of the configured regexes matched response: {raw_response!r}")

	# Derive whichever of weight/net is missing when we have enough data.
	if weight is None:
		weight = net if net is not None else gross
	if net is None and gross is not None and tare is not None:
		net = gross - tare

	for name, value in (("weight", weight), ("net_weight", net), ("gross_weight", gross)):
		if value is not None and value < 0 and not profile.get("negative_weight_allowed"):
			locals_map = {"weight": weight, "net_weight": net, "gross_weight": gross}
			locals_map[name] = abs(value)
			weight, net, gross = locals_map["weight"], locals_map["net_weight"], locals_map["gross_weight"]

	unit = _extract(raw_response, profile.get("unit_regex"))
	unit = unit.upper() if unit else None

	stable = None
	stable_pattern = profile.get("stable_regex")
	if stable_pattern:
		extracted = _extract(raw_response, stable_pattern)
		stable_value = profile.get("stable_value")
		stable = (extracted == stable_value) if stable_value else bool(extracted)

	return WeighingResult(
		weight=weight, gross_weight=gross, tare_weight=tare, net_weight=net,
		unit=unit, stable=stable, raw_response=raw_response,
	)
