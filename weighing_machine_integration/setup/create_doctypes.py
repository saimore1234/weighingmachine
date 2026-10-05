"""
One-off setup script that creates every DocType required by the
Weighing Machine Integration app.

Run once via:

	bench --site <site> execute weighing_machine_integration.setup.create_doctypes.execute

Relies on developer_mode=1 so that inserting a "DocType" document also
exports its .json/.py/.js files to disk under this app's module folder,
exactly like creating a DocType from the desk UI would.

Idempotent: re-running skips any DocType/Role that already exists.
"""

import itertools

import frappe

MODULE = "Weighing Machine Integration"

# Section/Column Break fieldnames are generated from a counter, never from
# the (human-readable, punctuation-containing) label - Frappe's column name
# validator rejects any non word character (e.g. "&", "/", ".", "(", ")").
_break_counter = itertools.count(1)


def _col(label):
	return {"fieldname": f"column_break_{next(_break_counter)}", "fieldtype": "Column Break", "label": label}


def _section(label, depends_on=None):
	d = {"fieldname": f"section_break_{next(_break_counter)}", "fieldtype": "Section Break", "label": label}
	if depends_on:
		d["depends_on"] = depends_on
	return d


def make_role(role_name):
	if frappe.db.exists("Role", role_name):
		return
	frappe.get_doc({
		"doctype": "Role",
		"role_name": role_name,
		"desk_access": 1,
	}).insert(ignore_permissions=True)


def default_perms(admin_role="System Manager", extra_roles=None):
	perms = [{
		"role": admin_role,
		"read": 1, "write": 1, "create": 1, "delete": 1,
		"report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
	}]
	for role, rights in (extra_roles or {}).items():
		row = {"role": role}
		row.update(rights)
		perms.append(row)
	return perms


def make_doctype(name, fields, permissions, autoname=None, istable=0, issingle=0,
				  track_changes=0, title_field=None, sort_field="modified", sort_order="DESC"):
	if frappe.db.exists("DocType", name):
		print(f"  - DocType already exists, skipping: {name}")
		return

	doc = frappe.get_doc({
		"doctype": "DocType",
		"name": name,
		"module": MODULE,
		"custom": 0,
		"istable": istable,
		"issingle": issingle,
		"editable_grid": 1 if istable else 0,
		"track_changes": track_changes,
		"sort_field": sort_field,
		"sort_order": sort_order,
		"fields": fields,
		"permissions": permissions,
	})
	if autoname:
		doc.autoname = autoname
	if title_field:
		doc.title_field = title_field

	doc.insert(ignore_permissions=True)
	print(f"  + Created DocType: {name}")


# ----------------------------------------------------------------------
# FIELD DEFINITIONS
# ----------------------------------------------------------------------

CONNECTION_TYPE_OPTIONS = "Serial\nTCP/IP\nHTTP API\nModbus TCP\nManual"
UOM_OPTIONS = "KG\nG\nLB\nTON"


def weighing_machine_fields():
	return [
		{"fieldname": "machine_name", "fieldtype": "Data", "label": "Machine Name", "reqd": 1, "unique": 1, "in_list_view": 1},
		{"fieldname": "enabled", "fieldtype": "Check", "label": "Enabled", "default": "1", "in_list_view": 1},
		{"fieldname": "connection_type", "fieldtype": "Select", "label": "Connection Type", "options": CONNECTION_TYPE_OPTIONS, "reqd": 1, "in_list_view": 1},
		_col("Machine Profile"),
		{"fieldname": "machine_profile", "fieldtype": "Link", "label": "Machine Profile", "options": "Weighing Machine Profile"},
		{"fieldname": "connection_mode", "fieldtype": "Select", "label": "Connection Mode", "options": "Server\nLocal Agent", "reqd": 1, "default": "Server"},
		_section("Details"),
		{"fieldname": "location", "fieldtype": "Data", "label": "Location"},
		{"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
		_col("Defaults"),
		{"fieldname": "default_uom", "fieldtype": "Select", "label": "Default UOM", "options": UOM_OPTIONS, "default": "KG"},
		{"fieldname": "active", "fieldtype": "Check", "label": "Active", "default": "1"},
		_section("Behaviour"),
		{"fieldname": "timeout", "fieldtype": "Int", "label": "Timeout (seconds)", "default": "5"},
		{"fieldname": "auto_reconnect", "fieldtype": "Check", "label": "Auto Reconnect", "default": "1"},
		{"fieldname": "read_interval", "fieldtype": "Float", "label": "Read Interval (seconds)", "default": "1"},
		_col("Stability"),
		{"fieldname": "require_stable_weight", "fieldtype": "Check", "label": "Require Stable Weight", "default": "0"},
		{"fieldname": "minimum_stable_readings", "fieldtype": "Int", "label": "Minimum Stable Readings", "default": "3",
		 "depends_on": "eval:doc.require_stable_weight"},
	]


def weighing_machine_profile_fields():
	return [
		{"fieldname": "profile_name", "fieldtype": "Data", "label": "Profile Name", "reqd": 1, "unique": 1, "in_list_view": 1},
		{"fieldname": "enabled", "fieldtype": "Check", "label": "Enabled", "default": "1"},
		{"fieldname": "connection_type", "fieldtype": "Select", "label": "Connection Type", "options": CONNECTION_TYPE_OPTIONS, "reqd": 1, "in_list_view": 1},
		_col("Identification"),
		{"fieldname": "manufacturer", "fieldtype": "Data", "label": "Manufacturer", "in_list_view": 1},
		{"fieldname": "model", "fieldtype": "Data", "label": "Model"},
		{"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},

		# -------------------- SERIAL --------------------
		_section("Serial Settings", depends_on="eval:doc.connection_type=='Serial'"),
		{"fieldname": "serial_port", "fieldtype": "Data", "label": "Port", "description": "e.g. COM3 or /dev/ttyUSB0"},
		{"fieldname": "baud_rate", "fieldtype": "Select", "label": "Baud Rate",
		 "options": "1200\n2400\n4800\n9600\n19200\n38400\n57600\n115200", "default": "9600"},
		{"fieldname": "data_bits", "fieldtype": "Select", "label": "Data Bits", "options": "5\n6\n7\n8", "default": "8"},
		_col("Serial Settings (cont.)"),
		{"fieldname": "stop_bits", "fieldtype": "Select", "label": "Stop Bits", "options": "1\n1.5\n2", "default": "1"},
		{"fieldname": "parity", "fieldtype": "Select", "label": "Parity", "options": "None\nEven\nOdd\nMark\nSpace", "default": "None"},
		{"fieldname": "serial_read_timeout", "fieldtype": "Float", "label": "Read Timeout (s)", "default": "2"},
		{"fieldname": "serial_write_timeout", "fieldtype": "Float", "label": "Write Timeout (s)", "default": "2"},
		{"fieldname": "serial_encoding", "fieldtype": "Data", "label": "Encoding", "default": "ascii"},
		{"fieldname": "serial_line_terminator", "fieldtype": "Data", "label": "Line Terminator", "default": "\\r\\n"},

		# -------------------- TCP --------------------
		_section("TCP Settings", depends_on="eval:doc.connection_type=='TCP/IP'"),
		{"fieldname": "tcp_host", "fieldtype": "Data", "label": "Host"},
		{"fieldname": "tcp_port", "fieldtype": "Int", "label": "Port", "default": "2000"},
		_col("TCP Settings (cont.)"),
		{"fieldname": "tcp_socket_timeout", "fieldtype": "Float", "label": "Socket Timeout (s)", "default": "5"},
		{"fieldname": "tcp_encoding", "fieldtype": "Data", "label": "Encoding", "default": "ascii"},
		{"fieldname": "tcp_terminator", "fieldtype": "Data", "label": "Terminator", "default": "\\r\\n"},

		# -------------------- HTTP --------------------
		_section("HTTP Settings", depends_on="eval:doc.connection_type=='HTTP API'"),
		{"fieldname": "http_url", "fieldtype": "Data", "label": "URL"},
		{"fieldname": "http_method", "fieldtype": "Select", "label": "HTTP Method", "options": "GET\nPOST\nPUT", "default": "GET"},
		{"fieldname": "http_headers", "fieldtype": "Code", "label": "Headers", "options": "JSON"},
		{"fieldname": "http_request_body", "fieldtype": "Code", "label": "Request Body", "options": "JSON"},
		_col("HTTP Auth"),
		{"fieldname": "http_auth_type", "fieldtype": "Select", "label": "Authentication Type",
		 "options": "None\nBasic\nBearer Token\nAPI Key Header", "default": "None"},
		{"fieldname": "http_username", "fieldtype": "Data", "label": "Username"},
		{"fieldname": "http_password", "fieldtype": "Password", "label": "Password"},
		{"fieldname": "http_token", "fieldtype": "Password", "label": "Token / API Key"},
		{"fieldname": "http_timeout", "fieldtype": "Float", "label": "Timeout (s)", "default": "5"},
		{"fieldname": "http_response_type", "fieldtype": "Select", "label": "Response Type", "options": "JSON\nText", "default": "JSON"},

		# -------------------- MODBUS --------------------
		_section("Modbus Settings", depends_on="eval:doc.connection_type=='Modbus TCP'"),
		{"fieldname": "modbus_host", "fieldtype": "Data", "label": "Host"},
		{"fieldname": "modbus_port", "fieldtype": "Int", "label": "Port", "default": "502"},
		{"fieldname": "modbus_slave_id", "fieldtype": "Int", "label": "Slave ID", "default": "1"},
		{"fieldname": "modbus_register", "fieldtype": "Int", "label": "Register"},
		_col("Modbus Settings (cont.)"),
		{"fieldname": "modbus_register_type", "fieldtype": "Select", "label": "Register Type",
		 "options": "Holding Register\nInput Register", "default": "Holding Register"},
		{"fieldname": "modbus_byte_order", "fieldtype": "Select", "label": "Byte Order", "options": "Big Endian\nLittle Endian", "default": "Big Endian"},
		{"fieldname": "modbus_word_order", "fieldtype": "Select", "label": "Word Order", "options": "Big Endian\nLittle Endian", "default": "Big Endian"},
		{"fieldname": "modbus_scale_factor", "fieldtype": "Float", "label": "Scale Factor", "default": "1"},
		{"fieldname": "modbus_offset", "fieldtype": "Float", "label": "Offset", "default": "0"},

		# -------------------- PARSING --------------------
		_section("Parsing Settings"),
		{"fieldname": "response_format", "fieldtype": "Select", "label": "Response Format",
		 "options": "Plain Numeric\nRegex\nJSON Path\nDelimited Gross/Tare/Net", "default": "Plain Numeric", "reqd": 1},
		{"fieldname": "weight_regex", "fieldtype": "Data", "label": "Weight Regex"},
		{"fieldname": "gross_weight_regex", "fieldtype": "Data", "label": "Gross Weight Regex"},
		{"fieldname": "tare_weight_regex", "fieldtype": "Data", "label": "Tare Weight Regex"},
		{"fieldname": "net_weight_regex", "fieldtype": "Data", "label": "Net Weight Regex"},
		{"fieldname": "unit_regex", "fieldtype": "Data", "label": "Unit Regex"},
		_col("Stability & JSON Paths"),
		{"fieldname": "stable_regex", "fieldtype": "Data", "label": "Stable Regex"},
		{"fieldname": "stable_value", "fieldtype": "Data", "label": "Stable Value"},
		{"fieldname": "weight_json_path", "fieldtype": "Data", "label": "Weight JSON Path"},
		{"fieldname": "gross_json_path", "fieldtype": "Data", "label": "Gross JSON Path"},
		{"fieldname": "tare_json_path", "fieldtype": "Data", "label": "Tare JSON Path"},
		{"fieldname": "net_json_path", "fieldtype": "Data", "label": "Net JSON Path"},
		{"fieldname": "unit_json_path", "fieldtype": "Data", "label": "Unit JSON Path"},
		{"fieldname": "stable_json_path", "fieldtype": "Data", "label": "Stable JSON Path"},
		_section("Number Format"),
		{"fieldname": "decimal_precision", "fieldtype": "Int", "label": "Decimal Precision", "default": "2"},
		{"fieldname": "decimal_separator", "fieldtype": "Data", "label": "Decimal Separator", "default": "."},
		_col("Number Format (cont.)"),
		{"fieldname": "thousands_separator", "fieldtype": "Data", "label": "Thousands Separator", "default": ""},
		{"fieldname": "negative_weight_allowed", "fieldtype": "Check", "label": "Negative Weight Allowed", "default": "0"},

		# -------------------- COMMANDS --------------------
		_section("Command Settings"),
		{"fieldname": "read_command", "fieldtype": "Data", "label": "Read Command"},
		{"fieldname": "zero_command", "fieldtype": "Data", "label": "Zero Command"},
		_col("Command Settings (cont.)"),
		{"fieldname": "tare_command", "fieldtype": "Data", "label": "Tare Command"},
		{"fieldname": "print_command", "fieldtype": "Data", "label": "Print Command"},
		{"fieldname": "command_terminator", "fieldtype": "Data", "label": "Command Terminator", "default": "\\r\\n"},
	]


def weighing_field_mapping_fields():
	return [
		{"fieldname": "mapping_name", "fieldtype": "Data", "label": "Mapping Name", "reqd": 1, "unique": 1, "in_list_view": 1},
		{"fieldname": "enabled", "fieldtype": "Check", "label": "Enabled", "default": "1", "in_list_view": 1},
		{"fieldname": "weighing_machine", "fieldtype": "Link", "label": "Weighing Machine", "options": "Weighing Machine"},
		_col("Target"),
		{"fieldname": "target_doctype", "fieldtype": "Link", "label": "Target DocType", "options": "DocType", "reqd": 1, "in_list_view": 1},
		{"fieldname": "is_child_table", "fieldtype": "Check", "label": "Is Child Table", "default": "0"},
		{"fieldname": "child_table_field", "fieldtype": "Data", "label": "Child Table Fieldname",
		 "depends_on": "eval:doc.is_child_table", "description": "Fieldname of the child table on the Target DocType"},

		_section("Parent Field Mapping", depends_on="eval:!doc.is_child_table"),
		{"fieldname": "target_weight_field", "fieldtype": "Data", "label": "Target Weight Field"},
		{"fieldname": "target_gross_weight_field", "fieldtype": "Data", "label": "Target Gross Weight Field"},
		{"fieldname": "target_tare_weight_field", "fieldtype": "Data", "label": "Target Tare Weight Field"},
		{"fieldname": "target_net_weight_field", "fieldtype": "Data", "label": "Target Net Weight Field"},
		_col("Parent Field Mapping (cont.)"),
		{"fieldname": "target_uom_field", "fieldtype": "Data", "label": "Target UOM Field"},
		{"fieldname": "target_stable_field", "fieldtype": "Data", "label": "Target Stable Field"},
		{"fieldname": "target_reading_reference_field", "fieldtype": "Data", "label": "Target Reading Reference Field"},
		{"fieldname": "target_timestamp_field", "fieldtype": "Data", "label": "Target Timestamp Field"},

		_section("Child Table Field Mapping", depends_on="eval:doc.is_child_table"),
		{"fieldname": "child_weight_field", "fieldtype": "Data", "label": "Child Weight Field"},
		{"fieldname": "child_gross_weight_field", "fieldtype": "Data", "label": "Child Gross Weight Field"},
		{"fieldname": "child_tare_weight_field", "fieldtype": "Data", "label": "Child Tare Weight Field"},
		_col("Child Table Field Mapping (cont.)"),
		{"fieldname": "child_net_weight_field", "fieldtype": "Data", "label": "Child Net Weight Field"},
		{"fieldname": "child_uom_field", "fieldtype": "Data", "label": "Child UOM Field"},
		{"fieldname": "child_stable_field", "fieldtype": "Data", "label": "Child Stable Field"},
		{"fieldname": "child_reading_reference_field", "fieldtype": "Data", "label": "Child Reading Reference Field"},

		_section("Behaviour"),
		{"fieldname": "require_stable_weight", "fieldtype": "Check", "label": "Require Stable Weight", "default": "0"},
		{"fieldname": "auto_capture", "fieldtype": "Check", "label": "Auto Capture", "default": "0"},
		{"fieldname": "allow_manual_weight", "fieldtype": "Check", "label": "Allow Manual Weight", "default": "1"},

		_section("Total Calculations (optional)"),
		{"fieldname": "total_weight_field", "fieldtype": "Data", "label": "Total Weight Field",
		 "description": "Parent field to auto-sum the configured child weight field into"},
		{"fieldname": "total_quantity_field", "fieldtype": "Data", "label": "Total Quantity Field"},
		{"fieldname": "total_net_weight_field", "fieldtype": "Data", "label": "Total Net Weight Field"},
	]


def weighing_reading_fields():
	return [
		{"fieldname": "reading_id", "fieldtype": "Data", "label": "Reading ID", "read_only": 1, "unique": 1, "in_list_view": 1},
		{"fieldname": "machine", "fieldtype": "Link", "label": "Machine", "options": "Weighing Machine", "in_list_view": 1, "in_standard_filter": 1},
		{"fieldname": "machine_profile", "fieldtype": "Link", "label": "Machine Profile", "options": "Weighing Machine Profile"},
		{"fieldname": "date_time", "fieldtype": "Datetime", "label": "Date Time", "default": "now", "in_list_view": 1},
		_col("Status"),
		{"fieldname": "user", "fieldtype": "Link", "label": "User", "options": "User", "default": "__user"},
		{"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Success\nUnstable\nError\nManual",
		 "in_list_view": 1, "in_standard_filter": 1},
		{"fieldname": "stable", "fieldtype": "Check", "label": "Stable"},

		_section("Weight"),
		{"fieldname": "gross_weight", "fieldtype": "Float", "label": "Gross Weight", "precision": "3"},
		{"fieldname": "tare_weight", "fieldtype": "Float", "label": "Tare Weight", "precision": "3"},
		_col("Weight (cont.)"),
		{"fieldname": "net_weight", "fieldtype": "Float", "label": "Net Weight", "precision": "3"},
		{"fieldname": "weight", "fieldtype": "Float", "label": "Weight", "precision": "3", "in_list_view": 1},
		{"fieldname": "uom", "fieldtype": "Data", "label": "UOM"},

		_section("Reference"),
		{"fieldname": "reference_doctype", "fieldtype": "Link", "label": "Reference DocType", "options": "DocType"},
		{"fieldname": "reference_document", "fieldtype": "Dynamic Link", "label": "Reference Document", "options": "reference_doctype"},
		{"fieldname": "reference_field", "fieldtype": "Data", "label": "Reference Field"},

		_section("Raw Data"),
		{"fieldname": "raw_response", "fieldtype": "Code", "label": "Raw Response", "read_only": 1},
		{"fieldname": "error_message", "fieldtype": "Small Text", "label": "Error Message"},
	]


def weighing_machine_log_fields():
	return [
		{"fieldname": "machine", "fieldtype": "Link", "label": "Machine", "options": "Weighing Machine", "in_list_view": 1, "in_standard_filter": 1},
		{"fieldname": "date_time", "fieldtype": "Datetime", "label": "Date Time", "default": "now", "in_list_view": 1},
		{"fieldname": "event", "fieldtype": "Select", "label": "Event",
		 "options": "Connection\nDisconnection\nRead\nError\nTimeout\nReconnect", "in_list_view": 1, "in_standard_filter": 1},
		_col("Status"),
		{"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Success\nFailure", "in_list_view": 1},
		{"fieldname": "user", "fieldtype": "Link", "label": "User", "options": "User", "default": "__user"},
		_section("Details"),
		{"fieldname": "message", "fieldtype": "Small Text", "label": "Message"},
		{"fieldname": "error", "fieldtype": "Small Text", "label": "Error"},
		{"fieldname": "raw_response", "fieldtype": "Code", "label": "Raw Response", "read_only": 1},
	]


def weighing_settings_fields():
	return [
		{"fieldname": "enable_integration", "fieldtype": "Check", "label": "Enable Integration", "default": "1"},
		{"fieldname": "allow_manual_weight", "fieldtype": "Check", "label": "Allow Manual Weight", "default": "1"},
		{"fieldname": "require_stable_weight", "fieldtype": "Check", "label": "Require Stable Weight", "default": "0"},
		_section("Defaults"),
		{"fieldname": "default_machine", "fieldtype": "Link", "label": "Default Machine", "options": "Weighing Machine"},
		{"fieldname": "default_profile", "fieldtype": "Link", "label": "Default Profile", "options": "Weighing Machine Profile"},
		_col("Defaults (cont.)"),
		{"fieldname": "default_uom", "fieldtype": "Select", "label": "Default UOM", "options": UOM_OPTIONS, "default": "KG"},
		{"fieldname": "default_timeout", "fieldtype": "Int", "label": "Default Timeout (s)", "default": "5"},

		_section("Weight Limits"),
		{"fieldname": "minimum_weight", "fieldtype": "Float", "label": "Minimum Weight"},
		{"fieldname": "maximum_weight", "fieldtype": "Float", "label": "Maximum Weight"},

		_section("Logging"),
		{"fieldname": "enable_logging", "fieldtype": "Check", "label": "Enable Logging", "default": "1"},
		{"fieldname": "log_level", "fieldtype": "Select", "label": "Log Level", "options": "Error\nWarning\nInfo\nDebug", "default": "Info"},

		_section("Local Agent"),
		{"fieldname": "enable_local_agent", "fieldtype": "Check", "label": "Enable Local Agent", "default": "0"},
		{"fieldname": "local_agent_url", "fieldtype": "Data", "label": "Local Agent URL",
		 "depends_on": "eval:doc.enable_local_agent"},
		{"fieldname": "local_agent_token", "fieldtype": "Password", "label": "Local Agent Token",
		 "depends_on": "eval:doc.enable_local_agent"},
	]


def execute():
	frappe.set_user("Administrator")

	print("Creating roles...")
	make_role("Weighing User")

	print("Creating DocTypes...")

	make_doctype(
		"Weighing Machine Profile",
		weighing_machine_profile_fields(),
		default_perms(extra_roles={"Weighing User": {"read": 1}}),
		autoname="field:profile_name",
		title_field="profile_name",
	)

	make_doctype(
		"Weighing Machine",
		weighing_machine_fields(),
		default_perms(extra_roles={"Weighing User": {"read": 1}}),
		autoname="field:machine_name",
		title_field="machine_name",
	)

	make_doctype(
		"Weighing Field Mapping",
		weighing_field_mapping_fields(),
		default_perms(extra_roles={"Weighing User": {"read": 1}}),
		autoname="field:mapping_name",
		title_field="mapping_name",
	)

	make_doctype(
		"Weighing Reading",
		weighing_reading_fields(),
		default_perms(extra_roles={"Weighing User": {"read": 1, "create": 1}}),
		autoname="field:reading_id",
		track_changes=1,
	)

	make_doctype(
		"Weighing Machine Log",
		weighing_machine_log_fields(),
		default_perms(extra_roles={"Weighing User": {"read": 1}}),
		autoname="format:WLOG-{#####}",
	)

	make_doctype(
		"Weighing Settings",
		weighing_settings_fields(),
		default_perms(extra_roles={"Weighing User": {"read": 1}}),
		issingle=1,
	)

	frappe.db.commit()
	print("Done.")
