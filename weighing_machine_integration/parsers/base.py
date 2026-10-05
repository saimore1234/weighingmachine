"""Standardized parse result shared by every parser implementation."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional


class ParseError(Exception):
	"""Raised when a raw machine response cannot be parsed into a weight."""


@dataclass
class WeighingResult:
	"""The single standardized object every parser must return.

	Drivers/services only ever deal with this shape, regardless of which
	machine, protocol, or response format produced it.
	"""

	weight: Optional[float] = None
	gross_weight: Optional[float] = None
	tare_weight: Optional[float] = None
	net_weight: Optional[float] = None
	unit: Optional[str] = None
	stable: Optional[bool] = None
	raw_response: str = ""
	timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

	def as_dict(self) -> dict:
		return {
			"weight": self.weight,
			"gross_weight": self.gross_weight,
			"tare_weight": self.tare_weight,
			"net_weight": self.net_weight,
			"unit": self.unit,
			"stable": self.stable,
			"raw_response": self.raw_response,
			"timestamp": self.timestamp,
		}

	def resolve_weight(self) -> Optional[float]:
		"""Best-effort single weight value.

		Falls back through weight -> net -> gross so callers always have a
		usable number when at least one of these was parsed.
		"""
		if self.weight is not None:
			return self.weight
		if self.net_weight is not None:
			return self.net_weight
		if self.gross_weight is not None:
			return self.gross_weight
		return None
