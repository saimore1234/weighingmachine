# Copyright (c) 2026, AITS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

_PARENT_FIELD_KEYS = (
	"target_weight_field", "target_gross_weight_field", "target_tare_weight_field",
	"target_net_weight_field", "target_uom_field", "target_stable_field",
	"target_reading_reference_field", "target_timestamp_field",
)
_CHILD_FIELD_KEYS = (
	"child_weight_field", "child_gross_weight_field", "child_tare_weight_field",
	"child_net_weight_field", "child_uom_field", "child_stable_field",
	"child_reading_reference_field",
)


class WeighingFieldMapping(Document):
	def validate(self):
		self.validate_target_doctype()
		self.validate_child_table_config()
		self.validate_configured_fields()

	def validate_target_doctype(self):
		if not frappe.db.exists("DocType", self.target_doctype):
			frappe.throw(_("Target DocType {0} does not exist").format(self.target_doctype))

	def validate_child_table_config(self):
		if not self.is_child_table:
			return
		if not self.child_table_field:
			frappe.throw(_("Child Table Fieldname is required when Is Child Table is checked"))

		meta = frappe.get_meta(self.target_doctype)
		field = meta.get_field(self.child_table_field)
		if not field or field.fieldtype != "Table":
			frappe.throw(
				_("{0} is not a child table field on {1}").format(self.child_table_field, self.target_doctype)
			)
		self._child_meta = frappe.get_meta(field.options)

	def validate_configured_fields(self):
		meta = frappe.get_meta(self.target_doctype)

		for key in _PARENT_FIELD_KEYS:
			fieldname = self.get(key)
			if fieldname and not meta.has_field(fieldname) and fieldname not in ("name", "owner", "modified"):
				frappe.throw(_("{0}: field {1} does not exist on {2}").format(key, fieldname, self.target_doctype))

		if self.is_child_table and getattr(self, "_child_meta", None):
			for key in _CHILD_FIELD_KEYS:
				fieldname = self.get(key)
				if fieldname and not self._child_meta.has_field(fieldname):
					frappe.throw(
						_("{0}: field {1} does not exist on child table {2}").format(
							key, fieldname, self._child_meta.name
						)
					)
