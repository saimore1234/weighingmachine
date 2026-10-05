/**
 * Generic "Capture Weight" injector.
 *
 * Loaded on every desk form (see hooks.py app_include_js). Looks up any
 * enabled Weighing Field Mapping(s) for the current form's DocType and, if
 * found, adds a "Capture Weight" button - either at document level (parent
 * field mapping) or on the configured child table's grid (child-table
 * mapping). No doctype/field name is hardcoded here; everything comes from
 * the Weighing Field Mapping record(s) returned by the server.
 */

(function () {
	if (window.weighing_capture_installed) return;
	window.weighing_capture_installed = true;

	const mapping_cache = {};

	function get_mappings(doctype) {
		if (mapping_cache[doctype]) {
			return Promise.resolve(mapping_cache[doctype]);
		}
		return frappe
			.xcall("weighing_machine_integration.api.weighing.get_mapping_for_doctype", {
				target_doctype: doctype,
			})
			.then((mappings) => {
				mapping_cache[doctype] = mappings || [];
				return mapping_cache[doctype];
			})
			.catch(() => []);
	}

	function prompt_for_machine(mapping, callback) {
		if (mapping.weighing_machine) {
			callback(mapping.weighing_machine, null);
			return;
		}
		frappe.call({
			method: "weighing_machine_integration.api.weighing.get_machines",
			callback: (r) => {
				const machines = r.message || [];
				if (!machines.length) {
					frappe.msgprint(__("No Weighing Machine is configured/enabled."));
					return;
				}
				if (machines.length === 1) {
					callback(machines[0].name, null);
					return;
				}
				const d = new frappe.ui.Dialog({
					title: __("Select Weighing Machine"),
					fields: [
						{
							fieldname: "machine",
							fieldtype: "Select",
							label: __("Machine"),
							options: machines.map((m) => m.name),
							reqd: 1,
						},
					],
					primary_action_label: __("Continue"),
					primary_action: (values) => {
						d.hide();
						callback(values.machine, null);
					},
				});
				d.show();
			},
		});
	}

	function do_capture(frm, mapping, child_row_name) {
		prompt_for_machine(mapping, (machine) => {
			frappe.dom.freeze(__("Reading weight..."));
			frappe
				.xcall("weighing_machine_integration.api.weighing.capture_weight", {
					mapping: mapping.name,
					target_doctype: frm.doctype,
					target_name: frm.docname,
					child_row_name: child_row_name,
				})
				.then((res) => {
					frappe.dom.unfreeze();
					frappe.show_alert({
						message: __("Captured weight: {0} {1}", [res.weight, res.unit || ""]),
						indicator: res.status === "Success" ? "green" : "orange",
					});
					frm.reload_doc();
				})
				.catch(() => frappe.dom.unfreeze());
		});
	}

	function add_parent_button(frm, mapping) {
		frm.add_custom_button(__("Capture Weight"), () => {
			if (frm.is_new()) {
				frappe.msgprint(__("Save the document first."));
				return;
			}
			do_capture(frm, mapping, null);
		});
	}

	function add_child_button(frm, mapping) {
		const grid_field = frm.fields_dict[mapping.child_table_field];
		if (!grid_field || !grid_field.grid) return;

		grid_field.grid.add_custom_button(__("Capture Weight"), () => {
			if (frm.is_new()) {
				frappe.msgprint(__("Save the document first."));
				return;
			}
			const selected = grid_field.grid.get_selected_children();
			const rows = frm.doc[mapping.child_table_field] || [];
			const row = selected && selected.length ? selected[0] : rows[rows.length - 1];
			if (!row) {
				frappe.msgprint(__("Add a row to {0} first.", [mapping.child_table_field]));
				return;
			}
			do_capture(frm, mapping, row.name);
		});
	}

	frappe.ui.form.on("*", {
		refresh(frm) {
			if (!frm.doctype) return;
			get_mappings(frm.doctype).then((mappings) => {
				mappings.forEach((mapping) => {
					if (mapping.is_child_table) {
						add_child_button(frm, mapping);
					} else {
						add_parent_button(frm, mapping);
					}
				});
			});
		},
	});
})();
