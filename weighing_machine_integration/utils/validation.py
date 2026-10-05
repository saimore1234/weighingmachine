"""Small, dependency-free validation/number-parsing helpers."""

from __future__ import annotations

from typing import Optional


def to_float(value, decimal_separator: str = ".", thousands_separator: str = "") -> Optional[float]:
	"""Convert a string using the admin-configured separators to a float.

	Returns None (never raises) when the value can't be parsed - callers
	decide whether that's an error.
	"""
	if value is None:
		return None
	if isinstance(value, (int, float)):
		return float(value)

	text = str(value).strip()
	if not text:
		return None

	if thousands_separator:
		text = text.replace(thousands_separator, "")
	if decimal_separator and decimal_separator != ".":
		text = text.replace(decimal_separator, ".")

	try:
		return float(text)
	except ValueError:
		return None


def clamp_precision(value: Optional[float], precision: int = 2) -> Optional[float]:
	if value is None:
		return None
	try:
		return round(float(value), int(precision))
	except (TypeError, ValueError):
		return value


def redact(text: Optional[str]) -> str:
	"""Best-effort redaction so secrets never land in logs."""
	if not text:
		return ""
	if len(text) <= 4:
		return "****"
	return text[:2] + "*" * (len(text) - 4) + text[-2:]
