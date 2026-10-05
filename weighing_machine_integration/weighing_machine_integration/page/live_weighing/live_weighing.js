frappe.pages["live-weighing"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Live Weighing",
		single_column: true,
	});

	new LiveWeighing(page);
};

class LiveWeighing {
	constructor(page) {
		this.page = page;
		this.machine = null;
		this.connected = false;
		this.render();
		this.load_machines();
	}

	render() {
		this.page.main.html(`
			<div class="live-weighing-wrapper" style="max-width: 640px; margin: 0 auto;">
				<div class="form-group">
					<label>Machine</label>
					<select class="form-control" data-field="machine"></select>
				</div>

				<div style="margin: 8px 0;">
					<span class="indicator-pill" data-field="status-pill" style="font-size: 13px;">
						<span class="indicator grey"></span> Not Connected
					</span>
				</div>

				<div class="text-center" style="margin: 24px 0; padding: 24px; border: 1px solid var(--border-color); border-radius: 8px;">
					<div data-field="weight" style="font-size: 48px; font-weight: 600;">--</div>
					<div data-field="uom" style="font-size: 16px; color: var(--text-muted);">UOM</div>
					<div style="margin-top: 8px;">
						<span class="indicator-pill" data-field="stable-pill">
							<span class="indicator grey"></span> Unknown
						</span>
					</div>
				</div>

				<div class="row text-center" style="margin-bottom: 16px;">
					<div class="col-sm-4">
						<div class="text-muted small">Gross</div>
						<div data-field="gross" style="font-size: 18px;">--</div>
					</div>
					<div class="col-sm-4">
						<div class="text-muted small">Tare</div>
						<div data-field="tare" style="font-size: 18px;">--</div>
					</div>
					<div class="col-sm-4">
						<div class="text-muted small">Net</div>
						<div data-field="net" style="font-size: 18px;">--</div>
					</div>
				</div>

				<div class="btn-group" style="display:flex; gap: 6px; flex-wrap: wrap;">
					<button class="btn btn-default btn-sm" data-action="connect">Connect</button>
					<button class="btn btn-default btn-sm" data-action="disconnect">Disconnect</button>
					<button class="btn btn-default btn-sm" data-action="test">Test Connection</button>
					<button class="btn btn-primary btn-sm" data-action="read">Read Weight</button>
					<button class="btn btn-success btn-sm" data-action="capture">Capture Weight</button>
					<button class="btn btn-default btn-sm" data-action="zero">Zero</button>
					<button class="btn btn-default btn-sm" data-action="tare">Tare</button>
				</div>

				<div data-field="raw-response-wrapper" style="margin-top: 16px; display: none;">
					<label class="text-muted small">Raw Response</label>
					<pre data-field="raw-response" style="font-size: 12px; max-height: 120px; overflow: auto;"></pre>
				</div>
			</div>
		`);

		this.$wrapper = this.page.main;
		this.$wrapper.find('[data-action="connect"]').on("click", () => this.connect());
		this.$wrapper.find('[data-action="disconnect"]').on("click", () => this.disconnect());
		this.$wrapper.find('[data-action="test"]').on("click", () => this.test_connection());
		this.$wrapper.find('[data-action="read"]').on("click", () => this.read_weight());
		this.$wrapper.find('[data-action="capture"]').on("click", () => this.capture_weight());
		this.$wrapper.find('[data-action="zero"]').on("click", () => this.zero());
		this.$wrapper.find('[data-action="tare"]').on("click", () => this.tare());
		this.$wrapper.find('[data-field="machine"]').on("change", (e) => {
			this.machine = e.target.value;
			this.set_status(false);
		});
	}

	load_machines() {
		frappe.call({
			method: "weighing_machine_integration.api.weighing.get_machines",
			callback: (r) => {
				const $select = this.$wrapper.find('[data-field="machine"]');
				$select.empty().append('<option value="">Select a machine...</option>');
				(r.message || []).forEach((m) => {
					$select.append(`<option value="${m.name}">${frappe.utils.escape_html(m.machine_name)} (${m.connection_type})</option>`);
				});
				if (r.message && r.message.length === 1) {
					$select.val(r.message[0].name).trigger("change");
				}
			},
		});
	}

	set_status(connected, label) {
		this.connected = connected;
		const $pill = this.$wrapper.find('[data-field="status-pill"]');
		$pill.html(
			`<span class="indicator ${connected ? "green" : "grey"}"></span> ${label || (connected ? "Connected" : "Not Connected")}`
		);
	}

	set_result(result) {
		this.$wrapper.find('[data-field="weight"]').text(result.weight != null ? result.weight : "--");
		this.$wrapper.find('[data-field="uom"]').text(result.unit || "");
		this.$wrapper.find('[data-field="gross"]').text(result.gross_weight != null ? result.gross_weight : "--");
		this.$wrapper.find('[data-field="tare"]').text(result.tare_weight != null ? result.tare_weight : "--");
		this.$wrapper.find('[data-field="net"]').text(result.net_weight != null ? result.net_weight : "--");

		const $stable = this.$wrapper.find('[data-field="stable-pill"]');
		if (result.stable === true) {
			$stable.html('<span class="indicator green"></span> Stable');
		} else if (result.stable === false) {
			$stable.html('<span class="indicator orange"></span> Unstable');
		} else {
			$stable.html('<span class="indicator grey"></span> Unknown');
		}

		if (result.raw_response) {
			this.$wrapper.find('[data-field="raw-response-wrapper"]').show();
			this.$wrapper.find('[data-field="raw-response"]').text(result.raw_response);
		}
	}

	require_machine() {
		if (!this.machine) {
			frappe.msgprint(__("Please select a machine first"));
			return false;
		}
		return true;
	}

	connect() {
		if (!this.require_machine()) return;
		frappe.call({
			method: "weighing_machine_integration.api.weighing.connect",
			args: { machine: this.machine },
			callback: (r) => {
				const ok = r.message && r.message.connected;
				this.set_status(ok, ok ? "Connected" : "Connection failed");
				if (!ok) frappe.msgprint({ title: __("Connection Failed"), message: (r.message.detail || {}).error || "Unknown error", indicator: "red" });
			},
		});
	}

	disconnect() {
		if (!this.require_machine()) return;
		frappe.call({
			method: "weighing_machine_integration.api.weighing.disconnect",
			args: { machine: this.machine },
			callback: () => this.set_status(false),
		});
	}

	test_connection() {
		if (!this.require_machine()) return;
		frappe.call({
			method: "weighing_machine_integration.api.weighing.test_connection",
			args: { machine: this.machine },
			freeze: true,
			freeze_message: __("Testing connection..."),
			callback: (r) => {
				const res = r.message || {};
				if (res.success) {
					this.set_status(true, `Connected (${res.elapsed_seconds}s)`);
					this.set_result(res);
					frappe.show_alert({ message: __("Connection OK"), indicator: "green" });
				} else {
					this.set_status(false, "Connection failed");
					frappe.msgprint({ title: __("Connection Failed"), message: res.error, indicator: "red" });
				}
			},
		});
	}

	read_weight() {
		if (!this.require_machine()) return;
		frappe.call({
			method: "weighing_machine_integration.api.weighing.read_weight",
			args: { machine: this.machine },
			freeze: true,
			freeze_message: __("Reading weight..."),
			callback: (r) => {
				const res = r.message || {};
				if (res.status === "Error") {
					frappe.msgprint({ title: __("Read Failed"), message: res.error_message, indicator: "red" });
					return;
				}
				this.set_status(true);
				this.set_result(res);
			},
		});
	}

	capture_weight() {
		if (!this.require_machine()) return;
		frappe.call({
			method: "weighing_machine_integration.api.weighing.capture_standalone_reading",
			args: { machine: this.machine },
			freeze: true,
			freeze_message: __("Capturing weight..."),
			callback: (r) => {
				const res = r.message || {};
				this.set_result(res);
				frappe.show_alert({ message: __("Captured as {0}", [res.reading]), indicator: "green" });
			},
		});
	}

	zero() {
		if (!this.require_machine()) return;
		frappe.call({
			method: "weighing_machine_integration.api.weighing.zero",
			args: { machine: this.machine },
			callback: (r) => {
				if (r.message && r.message.success) frappe.show_alert({ message: __("Zero sent"), indicator: "green" });
				else frappe.msgprint({ message: (r.message || {}).error, indicator: "red" });
			},
		});
	}

	tare() {
		if (!this.require_machine()) return;
		frappe.call({
			method: "weighing_machine_integration.api.weighing.tare",
			args: { machine: this.machine },
			callback: (r) => {
				if (r.message && r.message.success) frappe.show_alert({ message: __("Tare sent"), indicator: "green" });
				else frappe.msgprint({ message: (r.message || {}).error, indicator: "red" });
			},
		});
	}
}
