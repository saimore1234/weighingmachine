"""Configuration-driven JSON-path parser.

Supports simple dotted/bracket paths, e.g.:
	"data.weight"
	"data.items[0].weight"

No external jsonpath dependency - this tiny resolver covers the common
"field inside nested object/array" shapes real scale APIs use.
"""

from __future__ import annotations

import json
import re

from weighing_machine_integration.parsers.base import ParseError, WeighingResult
from weighing_machine_integration.utils.validation import clamp_precision, to_float

_TOKEN_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def resolve_path(data, path: str):
	if not path:
		return None

	current = data
	for name, index in _TOKEN_RE.findall(path):
		try:
			if name:
				current = current[name]
			elif index != "":
				current = current[int(index)]
		except (KeyError, IndexError, TypeError):
			return None
	return current


def parse(raw_response: str, profile) -> WeighingResult:
	if not raw_response or not raw_response.strip():
		raise ParseError("Empty response from machine")

	try:
		data = json.loads(raw_response)
	except json.JSONDecodeError as e:
		raise ParseError(f"Invalid JSON response: {e}")

	precision = profile.get("decimal_precision") or 2
	dec_sep = profile.get("decimal_separator") or "."
	thou_sep = profile.get("thousands_separator") or ""

	def num(path):
		raw = resolve_path(data, path)
		return clamp_precision(to_float(raw, dec_sep, thou_sep), precision) if raw is not None else None

	weight = num(profile.get("weight_json_path"))
	gross = num(profile.get("gross_json_path"))
	tare = num(profile.get("tare_json_path"))
	net = num(profile.get("net_json_path"))

	if weight is None and net is None and gross is None:
		raise ParseError(f"No configured JSON path matched response: {raw_response!r}")

	if weight is None:
		weight = net if net is not None else gross
	if net is None and gross is not None and tare is not None:
		net = gross - tare

	if weight is not None and weight < 0 and not profile.get("negative_weight_allowed"):
		weight = abs(weight)

	unit_raw = resolve_path(data, profile.get("unit_json_path"))
	unit = str(unit_raw).upper() if unit_raw is not None else None

	stable = None
	stable_path = profile.get("stable_json_path")
	if stable_path:
		stable_raw = resolve_path(data, stable_path)
		if isinstance(stable_raw, bool):
			stable = stable_raw
		elif stable_raw is not None:
			stable_value = profile.get("stable_value")
			stable = (str(stable_raw) == stable_value) if stable_value else bool(stable_raw)

	return WeighingResult(
		weight=weight, gross_weight=gross, tare_weight=tare, net_weight=net,
		unit=unit, stable=stable, raw_response=raw_response,
	)
