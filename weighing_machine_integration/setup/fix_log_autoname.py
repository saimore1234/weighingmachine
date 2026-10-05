import frappe


def execute():
	frappe.set_user("Administrator")
	doc = frappe.get_doc("DocType", "Weighing Machine Log")
	if doc.autoname != "format:WLOG-{#####}":
		doc.autoname = "format:WLOG-{#####}"
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		print("Fixed autoname to format:WLOG-{#####}")
	else:
		print("Already correct")
