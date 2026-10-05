# Copyright (c) 2026, AITS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WeighingMachine(Document):
	def validate(self):
		if self.enabled and not self.machine_profile:
			frappe.throw(_("Machine Profile is required when the machine is Enabled"))

		if self.machine_profile:
			profile_connection_type = frappe.db.get_value(
				"Weighing Machine Profile", self.machine_profile, "connection_type"
			)
			if profile_connection_type and profile_connection_type != self.connection_type:
				frappe.throw(
					_("Connection Type ({0}) does not match the selected Machine Profile's Connection Type ({1})").format(
						self.connection_type, profile_connection_type
					)
				)

		if self.require_stable_weight and not self.minimum_stable_readings:
			self.minimum_stable_readings = 3
