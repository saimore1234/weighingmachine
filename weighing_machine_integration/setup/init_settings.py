import frappe


def execute():
	"""Save Weighing Settings once so its declared field defaults are
	actually materialized into the DB (a Single's defaults otherwise only
	apply in-memory via frappe.get_doc(), not to raw db.get_single_value()
	reads, until the record has been saved at least once)."""
	frappe.set_user("Administrator")
	settings = frappe.get_single("Weighing Settings")
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	print("Weighing Settings initialized:", settings.as_dict())
