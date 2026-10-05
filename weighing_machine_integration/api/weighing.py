"""Whitelisted API surface. This is the only code the browser talks to -
every endpoint here is permission-checked and never executes arbitrary
input as code.
"""

from __future__ import annotations

import frappe

from weighing_machine_integration.services import machine_service, mapping_service


@frappe.whitelist()
def get_machines():
	frappe.has_permission("Weighing Machine", "read", throw=True)
	return frappe.get_all(
		"Weighing Machine",
		filters={"enabled": 1, "active": 1},
		fields=["name", "machine_name", "connection_type", "connection_mode", "default_uom", "require_stable_weight"],
		order_by="machine_name asc",
	)


@frappe.whitelist()
def test_connection(machine: str):
	frappe.has_permission("Weighing Machine", "read", throw=True)
	return machine_service.test_connection(machine)


@frappe.whitelist()
def connect(machine: str):
	"""Connections are opened per-operation (see machine_service module
	docstring for why); "Connect" verifies reachability without leaving
	anything open across requests."""
	frappe.has_permission("Weighing Machine", "read", throw=True)
	result = machine_service.test_connection(machine)
	return {"connected": result.get("success", False), "detail": result}


@frappe.whitelist()
def disconnect(machine: str):
	"""No persistent connection is ever held open server-side; this exists
	only so the UI has a symmetrical Disconnect action."""
	frappe.has_permission("Weighing Machine", "read", throw=True)
	return {"disconnected": True}


@frappe.whitelist()
def read_weight(machine: str, manual_value=None):
	frappe.has_permission("Weighing Machine", "read", throw=True)
	return machine_service.read_weight(machine, manual_value=manual_value)


@frappe.whitelist()
def zero(machine: str):
	frappe.has_permission("Weighing Machine", "write", throw=True)
	return machine_service.send_zero_or_tare(machine, "zero")


@frappe.whitelist()
def tare(machine: str):
	frappe.has_permission("Weighing Machine", "write", throw=True)
	return machine_service.send_zero_or_tare(machine, "tare")


@frappe.whitelist()
def get_mapping_for_doctype(target_doctype: str):
	"""Used by the generic client script to decide whether/how to show a
	"Capture Weight" button on a document."""
	if not frappe.has_permission(target_doctype, "read"):
		return []
	return mapping_service.get_mappings_for_doctype(target_doctype)


@frappe.whitelist()
def capture_standalone_reading(machine: str, manual_value=None):
	"""Used by the Live Weighing page's "Capture Weight" button: takes a
	reading and persists it as a Weighing Reading with no target document
	attached (not every capture is for a specific document)."""
	frappe.has_permission("Weighing Reading", "create", throw=True)

	result = machine_service.read_weight(machine, manual_value=manual_value)
	if result["status"] == "Error":
		frappe.throw(result["error_message"] or "Could not read weight")

	reading = frappe.get_doc({
		"doctype": "Weighing Reading",
		"machine": machine,
		"machine_profile": result.get("machine_profile"),
		"status": result["status"],
		"gross_weight": result["gross_weight"],
		"tare_weight": result["tare_weight"],
		"net_weight": result["net_weight"],
		"weight": result["weight"],
		"uom": result["unit"],
		"stable": 1 if result["stable"] else 0,
		"raw_response": result["raw_response"],
		"error_message": result.get("error_message"),
	}).insert(ignore_permissions=True)
	frappe.db.commit()

	result["reading"] = reading.name
	return result


@frappe.whitelist()
def capture_weight(mapping: str, target_doctype: str, target_name: str,
					child_row_name: str = None, manual_value=None):
	try:
		return mapping_service.capture_weight(
			mapping_name=mapping,
			target_doctype=target_doctype,
			target_name=target_name,
			child_row_name=child_row_name,
			manual_value=manual_value,
		)
	except mapping_service.MappingError as e:
		frappe.throw(str(e))
