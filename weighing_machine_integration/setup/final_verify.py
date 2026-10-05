import frappe


def execute():
	print("=== Installed apps ===")
	print(frappe.get_installed_apps())

	print("\n=== DocTypes ===")
	for dt in [
		"Weighing Machine", "Weighing Machine Profile", "Weighing Field Mapping",
		"Weighing Reading", "Weighing Machine Log", "Weighing Settings",
	]:
		exists = frappe.db.exists("DocType", dt)
		is_single = exists and frappe.get_meta(dt).issingle
		count = "N/A (Single)" if is_single else (frappe.db.count(dt) if exists else "N/A")
		print(f"  {dt}: exists={bool(exists)} row_count={count}")

	print("\n=== Page ===")
	print("  live-weighing exists:", bool(frappe.db.exists("Page", "live-weighing")))

	print("\n=== Roles ===")
	print("  Weighing User exists:", bool(frappe.db.exists("Role", "Weighing User")))

	print("\n=== Whitelisted API methods importable ===")
	from weighing_machine_integration.api import weighing
	for fn in ["get_machines", "test_connection", "connect", "disconnect", "read_weight",
			   "zero", "tare", "get_mapping_for_doctype", "capture_standalone_reading", "capture_weight"]:
		assert hasattr(weighing, fn), f"missing {fn}"
	print("  all 10 endpoints present")

	print("\nALL CHECKS PASSED")
