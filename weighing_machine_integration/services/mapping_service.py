"""Applies a captured weight to whatever ERPNext document/field the
administrator configured via a Weighing Field Mapping - parent fields or a
specific child-table row - and records a Weighing Reading audit entry.

This is the ONLY place that writes weight values onto a target document.
It never assumes a doctype/field name; everything comes from the Weighing
Field Mapping record.
"""

from __future__ import annotations

from typing import Optional

import frappe

from weighing_machine_integration.services import machine_service
from weighing_machine_integration.utils.validation import clamp_precision


class MappingError(Exception):
	pass


def get_mappings_for_doctype(target_doctype: str, only_enabled: bool = True):
	filters = {"target_doctype": target_doctype}
	if only_enabled:
		filters["enabled"] = 1
	return frappe.get_all(
		"Weighing Field Mapping",
		filters=filters,
		fields=[
			"name", "mapping_name", "weighing_machine", "is_child_table", "child_table_field",
			"require_stable_weight", "auto_capture", "allow_manual_weight",
		],
	)


def _set_if_configured(target, fieldname: Optional[str], value):
	if fieldname and value is not None:
		target.set(fieldname, value)


def _apply_totals(parent_doc, mapping):
	"""Sum a configured child field across all child rows into a parent field."""
	if not mapping.is_child_table or not mapping.child_table_field:
		return

	rows = parent_doc.get(mapping.child_table_field) or []

	def total_of(child_fieldname):
		return sum((row.get(child_fieldname) or 0) for row in rows)

	if mapping.total_weight_field and mapping.child_weight_field:
		parent_doc.set(mapping.total_weight_field, clamp_precision(total_of(mapping.child_weight_field), 3))
	if mapping.total_net_weight_field and mapping.child_net_weight_field:
		parent_doc.set(mapping.total_net_weight_field, clamp_precision(total_of(mapping.child_net_weight_field), 3))
	if mapping.total_quantity_field and mapping.child_weight_field:
		parent_doc.set(mapping.total_quantity_field, clamp_precision(total_of(mapping.child_weight_field), 3))


def capture_weight(mapping_name: str, target_doctype: str, target_name: str,
					child_row_name: Optional[str] = None, manual_value=None) -> dict:
	mapping = frappe.get_doc("Weighing Field Mapping", mapping_name)
	if not mapping.enabled:
		raise MappingError(f"Weighing Field Mapping {mapping_name!r} is disabled")
	if mapping.target_doctype != target_doctype:
		raise MappingError("Mapping does not belong to this DocType")
	if manual_value is not None and not mapping.allow_manual_weight:
		raise MappingError("Manual weight entry is not allowed for this mapping")

	reading_result = machine_service.read_weight(mapping.weighing_machine, manual_value=manual_value)
	if reading_result["status"] == "Error":
		raise MappingError(reading_result["error_message"] or "Could not read weight")
	if reading_result["status"] == "Unstable" and mapping.require_stable_weight:
		raise MappingError("Weight is not stable yet - try again")

	target_doc = frappe.get_doc(target_doctype, target_name)
	frappe.has_permission(target_doctype, "write", doc=target_doc, throw=True)

	if mapping.is_child_table:
		if not mapping.child_table_field:
			raise MappingError("Mapping has no Child Table Fieldname configured")
		rows = target_doc.get(mapping.child_table_field) or []
		row = next((r for r in rows if r.name == child_row_name), None) if child_row_name else (rows[-1] if rows else None)
		if row is None:
			raise MappingError("Could not find the target child row - add a row first")

		_set_if_configured(row, mapping.child_weight_field, reading_result["weight"])
		_set_if_configured(row, mapping.child_gross_weight_field, reading_result["gross_weight"])
		_set_if_configured(row, mapping.child_tare_weight_field, reading_result["tare_weight"])
		_set_if_configured(row, mapping.child_net_weight_field, reading_result["net_weight"])
		_set_if_configured(row, mapping.child_uom_field, reading_result["unit"])
		_set_if_configured(row, mapping.child_stable_field, reading_result["stable"])
		reference_field = mapping.child_reading_reference_field
		target_row_name = row.name
	else:
		_set_if_configured(target_doc, mapping.target_weight_field, reading_result["weight"])
		_set_if_configured(target_doc, mapping.target_gross_weight_field, reading_result["gross_weight"])
		_set_if_configured(target_doc, mapping.target_tare_weight_field, reading_result["tare_weight"])
		_set_if_configured(target_doc, mapping.target_net_weight_field, reading_result["net_weight"])
		_set_if_configured(target_doc, mapping.target_uom_field, reading_result["unit"])
		_set_if_configured(target_doc, mapping.target_stable_field, reading_result["stable"])
		if mapping.target_timestamp_field:
			target_doc.set(mapping.target_timestamp_field, frappe.utils.now())
		reference_field = mapping.target_reading_reference_field
		target_row_name = None

	_apply_totals(target_doc, mapping)

	# Create the audit Weighing Reading first so we have its name available
	# to stamp back onto the document's reference field.
	reading = frappe.get_doc({
		"doctype": "Weighing Reading",
		"machine": mapping.weighing_machine,
		"machine_profile": reading_result.get("machine_profile"),
		"status": reading_result["status"],
		"gross_weight": reading_result["gross_weight"],
		"tare_weight": reading_result["tare_weight"],
		"net_weight": reading_result["net_weight"],
		"weight": reading_result["weight"],
		"uom": reading_result["unit"],
		"stable": 1 if reading_result["stable"] else 0,
		"raw_response": reading_result["raw_response"],
		"reference_doctype": target_doctype,
		"reference_document": target_name,
		"reference_field": mapping.child_weight_field if mapping.is_child_table else mapping.target_weight_field,
		"error_message": reading_result.get("error_message"),
	}).insert(ignore_permissions=True)

	if reference_field:
		if mapping.is_child_table:
			row.set(reference_field, reading.name)
		else:
			target_doc.set(reference_field, reading.name)

	target_doc.save()
	frappe.db.commit()

	return {
		"reading": reading.name,
		"target_row": target_row_name,
		"weight": reading_result["weight"],
		"gross_weight": reading_result["gross_weight"],
		"tare_weight": reading_result["tare_weight"],
		"net_weight": reading_result["net_weight"],
		"unit": reading_result["unit"],
		"stable": reading_result["stable"],
		"status": reading_result["status"],
	}
