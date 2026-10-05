"""Single entrypoint: dispatches to the right parser based on the Weighing
Machine Profile's configured Response Format. Nothing else in the app
should import the individual parser modules directly.
"""

from __future__ import annotations

from weighing_machine_integration.parsers import json_parser, plain_parser, regex_parser
from weighing_machine_integration.parsers.base import ParseError, WeighingResult

_DISPATCH = {
	"Plain Numeric": plain_parser.parse,
	"Regex": regex_parser.parse,
	"Delimited Gross/Tare/Net": regex_parser.parse,
	"JSON Path": json_parser.parse,
}


def parse_response(raw_response: str, profile) -> WeighingResult:
	"""profile: a dict-like (Weighing Machine Profile doc or plain dict)."""
	response_format = profile.get("response_format") or "Plain Numeric"
	parser_fn = _DISPATCH.get(response_format)
	if not parser_fn:
		raise ParseError(f"Unsupported response format: {response_format!r}")
	return parser_fn(raw_response, profile)


__all__ = ["parse_response", "ParseError", "WeighingResult"]
