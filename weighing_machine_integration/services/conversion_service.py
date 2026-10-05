"""Weight unit conversion. Pure functions, no Frappe dependency."""

from __future__ import annotations

from typing import Optional

# Conversion factor TO kilograms.
_TO_KG = {
	"KG": 1.0,
	"G": 0.001,
	"LB": 0.45359237,
	"TON": 1000.0,
}


def to_kg(value: float, unit: str) -> float:
	unit = (unit or "KG").upper()
	if unit not in _TO_KG:
		raise ValueError(f"Unknown weight unit: {unit!r}")
	return value * _TO_KG[unit]


def convert(value: Optional[float], from_unit: str, to_unit: str) -> Optional[float]:
	if value is None:
		return None
	from_unit = (from_unit or "KG").upper()
	to_unit = (to_unit or "KG").upper()
	if from_unit == to_unit:
		return value
	if from_unit not in _TO_KG:
		raise ValueError(f"Unknown weight unit: {from_unit!r}")
	if to_unit not in _TO_KG:
		raise ValueError(f"Unknown weight unit: {to_unit!r}")
	return (value * _TO_KG[from_unit]) / _TO_KG[to_unit]


def supported_units():
	return tuple(_TO_KG.keys())
