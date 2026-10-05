"""Field Mapping integration tests - parent fields AND child-table rows,
against temporary throwaway DocTypes created just for this test (so we
never depend on / risk any real ERPNext doctype). The actual machine read
is mocked - this test is about the mapping/field-writing logic, not the
driver layer (see test_drivers.py for that).
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from weighing_machine_integration.services import mapping_service

PARENT_DOCTYPE = "Test Weighing Target"
CHILD_DOCTYPE = "Test Weighing Target Item"

FAKE_READING = {
	"status": "Success", "weight": 123.45, "gross_weight": 133.45, "tare_weight": 10.0,
	"net_weight": 123.45, "unit": "KG", "stable": True, "raw_response": "123.45 kg",
	"error_message": None, "machine_profile": None,
}


def _make_test_doctypes():
	if not frappe.db.exists("DocType", CHILD_DOCTYPE):
		frappe.get_doc({
			"doctype": "DocType",
			"name": CHILD_DOCTYPE,
			"module": "Weighing Machine Integration",
			"custom": 1,
			"istable": 1,
			"fields": [
				{"fieldname": "item_label", "fieldtype": "Data", "label": "Item"},
				{"fieldname": "captured_weight", "fieldtype": "Float", "label": "Weight"},
				{"fieldname": "captured_uom", "fieldtype": "Data", "label": "UOM"},
				{"fieldname": "captured_stable", "fieldtype": "Check", "label": "Stable"},
				{"fieldname": "reading_ref", "fieldtype": "Data", "label": "Reading Ref"},
			],
			"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("DocType", PARENT_DOCTYPE):
		frappe.get_doc({
			"doctype": "DocType",
			"name": PARENT_DOCTYPE,
			"module": "Weighing Machine Integration",
			"custom": 1,
			"fields": [
				{"fieldname": "title", "fieldtype": "Data", "label": "Title"},
				{"fieldname": "captured_weight", "fieldtype": "Float", "label": "Weight"},
				{"fieldname": "captured_uom", "fieldtype": "Data", "label": "UOM"},
				{"fieldname": "reading_ref", "fieldtype": "Data", "label": "Reading Ref"},
				{"fieldname": "total_weight", "fieldtype": "Float", "label": "Total Weight"},
				{"fieldname": "items", "fieldtype": "Table", "label": "Items", "options": CHILD_DOCTYPE},
			],
			"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}],
		}).insert(ignore_permissions=True)


class TestFieldMapping(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		_make_test_doctypes()

	def setUp(self):
		# A disabled/dummy machine is enough - machine_service.read_weight is mocked.
		if not frappe.db.exists("Weighing Machine Profile", "TEST-PROFILE"):
			frappe.get_doc({
				"doctype": "Weighing Machine Profile", "profile_name": "TEST-PROFILE",
				"connection_type": "Manual", "response_format": "Plain Numeric",
			}).insert(ignore_permissions=True)
		if not frappe.db.exists("Weighing Machine", "TEST-MACHINE"):
			frappe.get_doc({
				"doctype": "Weighing Machine", "machine_name": "TEST-MACHINE",
				"connection_type": "Manual", "connection_mode": "Server",
				"machine_profile": "TEST-PROFILE", "enabled": 1, "active": 1,
			}).insert(ignore_permissions=True)

	def _make_mapping(self, **overrides):
		data = {
			"doctype": "Weighing Field Mapping",
			"mapping_name": frappe.generate_hash(length=8),
			"enabled": 1,
			"weighing_machine": "TEST-MACHINE",
			"target_doctype": PARENT_DOCTYPE,
		}
		data.update(overrides)
		return frappe.get_doc(data).insert(ignore_permissions=True)

	@patch("weighing_machine_integration.services.machine_service.read_weight", return_value=FAKE_READING)
	def test_parent_field_mapping(self, _mock_read):
		mapping = self._make_mapping(
			target_weight_field="captured_weight",
			target_uom_field="captured_uom",
			target_reading_reference_field="reading_ref",
		)
		doc = frappe.get_doc({"doctype": PARENT_DOCTYPE, "title": "Parent mapping test"}).insert(ignore_permissions=True)

		result = mapping_service.capture_weight(mapping.name, PARENT_DOCTYPE, doc.name)

		doc.reload()
		self.assertEqual(doc.captured_weight, 123.45)
		self.assertEqual(doc.captured_uom, "KG")
		self.assertEqual(doc.reading_ref, result["reading"])
		self.assertTrue(frappe.db.exists("Weighing Reading", result["reading"]))

	@patch("weighing_machine_integration.services.machine_service.read_weight", return_value=FAKE_READING)
	def test_child_table_mapping_with_totals(self, _mock_read):
		mapping = self._make_mapping(
			is_child_table=1, child_table_field="items",
			child_weight_field="captured_weight", child_uom_field="captured_uom",
			child_reading_reference_field="reading_ref",
			total_weight_field="total_weight",
		)
		doc = frappe.get_doc({
			"doctype": PARENT_DOCTYPE, "title": "Child mapping test",
			"items": [{"item_label": "Row 1"}],
		}).insert(ignore_permissions=True)
		row_name = doc.items[0].name

		mapping_service.capture_weight(mapping.name, PARENT_DOCTYPE, doc.name, child_row_name=row_name)

		doc.reload()
		self.assertEqual(doc.items[0].captured_weight, 123.45)
		self.assertEqual(doc.items[0].captured_uom, "KG")
		self.assertEqual(doc.total_weight, 123.45)

	@patch("weighing_machine_integration.services.machine_service.read_weight", return_value=FAKE_READING)
	def test_child_table_totals_sum_multiple_rows(self, _mock_read):
		mapping = self._make_mapping(
			is_child_table=1, child_table_field="items",
			child_weight_field="captured_weight",
			total_weight_field="total_weight",
		)
		doc = frappe.get_doc({
			"doctype": PARENT_DOCTYPE, "title": "Multi-row totals test",
			"items": [{"item_label": "Row 1", "captured_weight": 50}, {"item_label": "Row 2"}],
		}).insert(ignore_permissions=True)
		row2_name = doc.items[1].name

		mapping_service.capture_weight(mapping.name, PARENT_DOCTYPE, doc.name, child_row_name=row2_name)

		doc.reload()
		self.assertEqual(doc.total_weight, 50 + 123.45)

	def test_disabled_mapping_raises(self):
		mapping = self._make_mapping(enabled=0, target_weight_field="captured_weight")
		doc = frappe.get_doc({"doctype": PARENT_DOCTYPE, "title": "Disabled mapping test"}).insert(ignore_permissions=True)
		with self.assertRaises(mapping_service.MappingError):
			mapping_service.capture_weight(mapping.name, PARENT_DOCTYPE, doc.name)

	@patch("weighing_machine_integration.services.machine_service.read_weight",
		   return_value={**FAKE_READING, "status": "Error", "error_message": "Machine offline"})
	def test_read_error_raises_and_does_not_touch_document(self, _mock_read):
		mapping = self._make_mapping(target_weight_field="captured_weight")
		doc = frappe.get_doc({"doctype": PARENT_DOCTYPE, "title": "Error test"}).insert(ignore_permissions=True)

		with self.assertRaises(mapping_service.MappingError):
			mapping_service.capture_weight(mapping.name, PARENT_DOCTYPE, doc.name)

		doc.reload()
		self.assertFalse(doc.captured_weight)

	@patch("weighing_machine_integration.services.machine_service.read_weight",
		   return_value={**FAKE_READING, "status": "Unstable", "stable": False})
	def test_unstable_reading_rejected_when_required(self, _mock_read):
		mapping = self._make_mapping(target_weight_field="captured_weight", require_stable_weight=1)
		doc = frappe.get_doc({"doctype": PARENT_DOCTYPE, "title": "Unstable test"}).insert(ignore_permissions=True)

		with self.assertRaises(mapping_service.MappingError):
			mapping_service.capture_weight(mapping.name, PARENT_DOCTYPE, doc.name)

	def test_missing_child_row_raises(self):
		mapping = self._make_mapping(is_child_table=1, child_table_field="items", child_weight_field="captured_weight")
		doc = frappe.get_doc({"doctype": PARENT_DOCTYPE, "title": "No rows test"}).insert(ignore_permissions=True)

		with self.assertRaises(mapping_service.MappingError):
			mapping_service.capture_weight(mapping.name, PARENT_DOCTYPE, doc.name, child_row_name="nonexistent")
