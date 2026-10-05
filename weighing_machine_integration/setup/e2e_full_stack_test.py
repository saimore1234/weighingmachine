"""The real end-to-end test: creates actual Weighing Machine + Weighing
Machine Profile + Weighing Field Mapping documents (not mocks), points
them at the live TCP simulator, and drives a capture all the way through
machine_service -> driver -> parser -> Weighing Reading -> mapping_service
-> a target document. This is what the spec calls the final validation
chain: Simulator -> Driver -> Parser -> Weighing Reading -> ERPNext API ->
Field Mapping -> Target Document.
"""

import frappe

from weighing_machine_integration.services import machine_service, mapping_service

PARENT_DOCTYPE = "Test Weighing Target"


def execute():
	frappe.set_user("Administrator")

	# 1) Profile pointed at the live TCP simulator (port 19001, Plain Numeric)
	if frappe.db.exists("Weighing Machine Profile", "E2E-TCP-PROFILE"):
		frappe.delete_doc("Weighing Machine Profile", "E2E-TCP-PROFILE", force=1, ignore_permissions=True)
	profile = frappe.get_doc({
		"doctype": "Weighing Machine Profile",
		"profile_name": "E2E-TCP-PROFILE",
		"connection_type": "TCP/IP",
		"tcp_host": "127.0.0.1",
		"tcp_port": 19001,
		"tcp_socket_timeout": 5,
		"response_format": "Plain Numeric",
		"decimal_precision": 2,
		"enabled": 1,
	}).insert(ignore_permissions=True)

	# 2) Machine using that profile
	if frappe.db.exists("Weighing Machine", "E2E-TCP-MACHINE"):
		frappe.delete_doc("Weighing Machine", "E2E-TCP-MACHINE", force=1, ignore_permissions=True)
	machine = frappe.get_doc({
		"doctype": "Weighing Machine",
		"machine_name": "E2E-TCP-MACHINE",
		"enabled": 1,
		"active": 1,
		"connection_type": "TCP/IP",
		"connection_mode": "Server",
		"machine_profile": profile.name,
		"default_uom": "KG",
	}).insert(ignore_permissions=True)

	# 3) Drive it through machine_service directly (this is what Test
	#    Connection / Read Weight / Live Weighing page all call).
	result = machine_service.read_weight(machine.name)
	print("machine_service.read_weight ->", result)
	assert result["status"] == "Success", result
	assert result["weight"] is not None

	log_count = frappe.db.count("Weighing Machine Log", {"machine": machine.name})
	assert log_count >= 2, f"expected Connection+Read log entries, got {log_count}"
	print(f"Weighing Machine Log entries for this machine: {log_count}")

	# 4) Now the full Field Mapping path onto a real target document.
	if not frappe.db.exists("DocType", PARENT_DOCTYPE):
		raise RuntimeError(f"{PARENT_DOCTYPE} doctype missing - run test_mapping.py's doctype setup first "
							"(it's created automatically when the test suite runs)")

	mapping_name = None
	existing = frappe.get_all("Weighing Field Mapping", filters={"mapping_name": "E2E-MAPPING"})
	if existing:
		mapping_name = existing[0].name
	else:
		mapping = frappe.get_doc({
			"doctype": "Weighing Field Mapping",
			"mapping_name": "E2E-MAPPING",
			"enabled": 1,
			"weighing_machine": machine.name,
			"target_doctype": PARENT_DOCTYPE,
			"target_weight_field": "captured_weight",
			"target_uom_field": "captured_uom",
			"target_reading_reference_field": "reading_ref",
		}).insert(ignore_permissions=True)
		mapping_name = mapping.name

	target = frappe.get_doc({"doctype": PARENT_DOCTYPE, "title": "E2E full stack target"}).insert(ignore_permissions=True)
	capture_result = mapping_service.capture_weight(mapping_name, PARENT_DOCTYPE, target.name)
	print("mapping_service.capture_weight ->", capture_result)

	target.reload()
	assert target.captured_weight == capture_result["weight"]
	assert target.captured_uom == "KG"
	assert target.reading_ref == capture_result["reading"]
	assert frappe.db.exists("Weighing Reading", capture_result["reading"])

	frappe.db.commit()
	print("\nFULL STACK END-TO-END TEST: ALL PASSED")
	print(f"  Weighing Reading: {capture_result['reading']}")
	print(f"  Target document: {PARENT_DOCTYPE} {target.name} captured_weight={target.captured_weight}")
