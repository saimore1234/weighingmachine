# Copyright (c) 2026, AITS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WeighingMachineProfile(Document):
	def validate(self):
		self.validate_connection_settings()
		self.validate_parsing_settings()

	def validate_connection_settings(self):
		required_by_type = {
			"Serial": ("serial_port", _("Port")),
			"TCP/IP": ("tcp_host", _("Host")),
			"HTTP API": ("http_url", _("URL")),
			"Modbus TCP": ("modbus_host", _("Host")),
		}
		requirement = required_by_type.get(self.connection_type)
		if requirement:
			fieldname, label = requirement
			if not self.get(fieldname):
				frappe.throw(_("{0} is required for Connection Type {1}").format(label, self.connection_type))

	def validate_parsing_settings(self):
		if self.connection_type == "Manual":
			return

		if self.response_format == "Regex" and not self.weight_regex:
			frappe.throw(_("Weight Regex is required when Response Format is Regex"))

		if self.response_format == "Delimited Gross/Tare/Net" and not any(
			[self.gross_weight_regex, self.tare_weight_regex, self.net_weight_regex]
		):
			frappe.throw(_("At least one of Gross/Tare/Net Weight Regex is required for this Response Format"))

		if self.response_format == "JSON Path" and not self.weight_json_path and not any(
			[self.gross_json_path, self.net_json_path]
		):
			frappe.throw(_("Weight JSON Path (or Gross/Net JSON Path) is required when Response Format is JSON Path"))
