import frappe


def execute():
	frappe.set_user("Administrator")
	doc = frappe.get_doc("DocType", "Weighing Machine Profile")
	fieldnames = [f.fieldname for f in doc.fields]

	if "stability_tolerance" not in fieldnames:
		doc.append("fields", {
			"fieldname": "stability_tolerance",
			"fieldtype": "Float",
			"label": "Stability Tolerance",
			"default": "0.02",
			"description": "Max allowed difference between consecutive readings to be considered stable",
		})
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		print("Added stability_tolerance field")
	else:
		print("Field already exists")
