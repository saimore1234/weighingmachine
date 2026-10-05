import frappe


def execute():
	print("=== Weighing Machine Log rows ===")
	rows = frappe.get_all("Weighing Machine Log", fields=["name", "machine", "event", "status", "error", "creation"],
						   order_by="creation desc", limit=10)
	for r in rows:
		print(r)

	print("\n=== Recent Error Log entries mentioning weighing ===")
	errors = frappe.get_all(
		"Error Log",
		filters=[["error", "like", "%weighing%"]],
		fields=["name", "method", "creation"],
		order_by="creation desc",
		limit=5,
	)
	for e in errors:
		doc = frappe.get_doc("Error Log", e.name)
		print("----", e.name, e.creation)
		print(doc.error[:2000])
