import frappe

MODULE = "Weighing Machine Integration"


def execute():
	frappe.set_user("Administrator")

	if frappe.db.exists("Page", "live-weighing"):
		print("Page already exists, skipping")
		return

	frappe.get_doc({
		"doctype": "Page",
		"name": "live-weighing",
		"page_name": "live-weighing",
		"title": "Live Weighing",
		"module": MODULE,
		"standard": "Yes",
		"roles": [{"role": "Weighing User"}, {"role": "System Manager"}],
	}).insert(ignore_permissions=True)

	frappe.db.commit()
	print("Created Page: live-weighing")
