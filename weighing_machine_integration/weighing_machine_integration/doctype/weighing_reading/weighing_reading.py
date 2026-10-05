# Copyright (c) 2026, AITS and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.model.naming import make_autoname


class WeighingReading(Document):
	def autoname(self):
		# autoname = "field:reading_id", but nothing sets reading_id on
		# creation - generate it here so callers never have to.
		if not self.reading_id:
			self.reading_id = make_autoname("WR-.#####")
		self.name = self.reading_id
