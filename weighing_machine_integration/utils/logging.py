"""Writes Weighing Machine Log entries and routes technical errors to
frappe's error log. Never writes passwords/tokens anywhere.
"""

from __future__ import annotations

import frappe

from weighing_machine_integration.utils.constants import SENSITIVE_FIELDS


def _settings_allow_logging() -> bool:
	try:
		value = frappe.db.get_single_value("Weighing Settings", "enable_logging")
		# None means the Single has never been saved yet (so the field's
		# own "default": "1" was never materialized into the DB) - treat
		# that the same as enabled, not disabled.
		return True if value is None else bool(value)
	except Exception:
		return True


def scrub(text):
	"""Defensive scrub in case a raw response happens to echo back a
	configured secret (some APIs do this in error payloads)."""
	if not text:
		return text
	text = str(text)
	for key in SENSITIVE_FIELDS:
		if key in text.lower():
			return "[redacted - response referenced a sensitive field name]"
	return text


def log_machine_event(machine, event, status, message=None, raw_response=None, error=None):
	"""machine: Weighing Machine name (str) or None."""
	if not _settings_allow_logging():
		return

	try:
		frappe.get_doc({
			"doctype": "Weighing Machine Log",
			"machine": machine,
			"event": event,
			"status": status,
			"message": scrub(message),
			"raw_response": scrub(raw_response),
			"error": scrub(error),
			"user": frappe.session.user if frappe.session else None,
		}).insert(ignore_permissions=True)
	except Exception:
		# Logging must never break the actual weighing operation.
		frappe.log_error(title="weighing_machine_integration: failed to write Weighing Machine Log",
						  message=frappe.get_traceback())
