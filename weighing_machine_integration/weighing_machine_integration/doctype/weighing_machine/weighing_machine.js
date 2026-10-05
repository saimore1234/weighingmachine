// Copyright (c) 2026, AITS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Weighing Machine", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: "weighing_machine_integration.api.weighing.test_connection",
				args: { machine: frm.doc.name },
				freeze: true,
				freeze_message: __("Testing connection..."),
				callback: (r) => {
					const res = r.message || {};
					if (res.success) {
						frappe.msgprint({
							title: __("Connection Successful"),
							indicator: "green",
							message: `
								<b>${__("Weight")}:</b> ${res.weight ?? "-"} ${res.unit ?? ""}<br>
								<b>${__("Stable")}:</b> ${res.stable == null ? "-" : res.stable}<br>
								<b>${__("Elapsed")}:</b> ${res.elapsed_seconds}s<br>
								<b>${__("Raw Response")}:</b> <pre>${frappe.utils.escape_html(res.raw_response || "")}</pre>
							`,
						});
					} else {
						frappe.msgprint({
							title: __("Connection Failed"),
							indicator: "red",
							message: `${__("Error")}: ${frappe.utils.escape_html(res.error || "Unknown error")}<br>${__("Elapsed")}: ${res.elapsed_seconds}s`,
						});
					}
				},
			});
		});

		frm.add_custom_button(__("Read Test Weight"), () => {
			frappe.call({
				method: "weighing_machine_integration.api.weighing.read_weight",
				args: { machine: frm.doc.name },
				freeze: true,
				freeze_message: __("Reading..."),
				callback: (r) => {
					const res = r.message || {};
					if (res.status === "Error") {
						frappe.msgprint({ title: __("Read Failed"), indicator: "red", message: res.error_message });
						return;
					}
					frappe.msgprint({
						title: __("Weight Reading"),
						indicator: res.status === "Success" ? "green" : "orange",
						message: `
							<b>${__("Status")}:</b> ${res.status}<br>
							<b>${__("Weight")}:</b> ${res.weight ?? "-"} ${res.unit ?? ""}<br>
							<b>${__("Gross")}:</b> ${res.gross_weight ?? "-"}
							&nbsp;<b>${__("Tare")}:</b> ${res.tare_weight ?? "-"}
							&nbsp;<b>${__("Net")}:</b> ${res.net_weight ?? "-"}<br>
							<b>${__("Stable")}:</b> ${res.stable == null ? "-" : res.stable}
						`,
					});
				},
			});
		});

		if (frm.doc.connection_type !== "Manual") {
			frm.add_custom_button(__("Zero"), () => {
				frappe.call({ method: "weighing_machine_integration.api.weighing.zero", args: { machine: frm.doc.name } });
			}, __("Commands"));
			frm.add_custom_button(__("Tare"), () => {
				frappe.call({ method: "weighing_machine_integration.api.weighing.tare", args: { machine: frm.doc.name } });
			}, __("Commands"));
		}
	},
});
