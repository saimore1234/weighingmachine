"""Orchestrates: load Machine + Profile -> build driver -> connect -> read
-> (optionally wait for stability) -> disconnect, with Weighing Machine Log
entries at every step.

Design note - connection lifetime:
	A Frappe site typically runs multiple worker processes. Holding a
	Serial/TCP socket open *across* HTTP requests is unsafe in that
	environment (the next request can land on a different worker that has
	no handle to the already-open port, or two workers could race to open
	the same COM port). So every operation here is connect -> read ->
	disconnect as one atomic call. This is simpler and safer than faking
	persistent state, at the cost of a reconnect per read - acceptable for
	interactive weighing and what "Auto Reconnect" on the Machine doctype
	is about.
"""

from __future__ import annotations

import frappe

from weighing_machine_integration.drivers.base import DriverError
from weighing_machine_integration.drivers.registry import create_driver
from weighing_machine_integration.services.stability_service import take_stable_reading
from weighing_machine_integration.utils import logging as wlog
from weighing_machine_integration.utils.constants import (
	LOG_EVENT_CONNECTION, LOG_EVENT_DISCONNECTION, LOG_EVENT_ERROR,
	LOG_EVENT_READ, LOG_EVENT_TIMEOUT, LOG_STATUS_FAILURE, LOG_STATUS_SUCCESS,
)


class MachineNotFound(Exception):
	pass


def get_machine_and_profile(machine_name: str):
	if not machine_name:
		raise MachineNotFound("No machine specified")
	if not frappe.db.exists("Weighing Machine", machine_name):
		raise MachineNotFound(f"Weighing Machine {machine_name!r} does not exist")

	machine = frappe.get_doc("Weighing Machine", machine_name)
	if not machine.enabled or not machine.active:
		raise MachineNotFound(f"Weighing Machine {machine_name!r} is disabled/inactive")
	if not machine.machine_profile:
		raise MachineNotFound(f"Weighing Machine {machine_name!r} has no Machine Profile configured")

	profile = frappe.get_doc("Weighing Machine Profile", machine.machine_profile)
	if not profile.enabled:
		raise MachineNotFound(f"Machine Profile {machine.machine_profile!r} is disabled")

	return machine, profile


def _profile_to_dict(profile) -> dict:
	"""What gets sent to a Local Agent - the agent needs these values to
	open its own connection to the hardware attached to that PC."""
	skip = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx"}
	return {k: v for k, v in profile.as_dict().items() if k not in skip and not k.startswith("_")}


def test_connection(machine_name: str) -> dict:
	machine, profile = get_machine_and_profile(machine_name)

	if machine.connection_mode == "Local Agent":
		from weighing_machine_integration.services import local_agent_client
		try:
			result = local_agent_client.test_connection(machine.name, profile=_profile_to_dict(profile))
		except Exception as e:
			result = {"success": False, "error": str(e)}
	else:
		driver = create_driver(profile)
		result = driver.test_connection()

	wlog.log_machine_event(
		machine.name,
		LOG_EVENT_CONNECTION if result.get("success") else LOG_EVENT_ERROR,
		LOG_STATUS_SUCCESS if result.get("success") else LOG_STATUS_FAILURE,
		message="Test Connection",
		raw_response=result.get("raw_response"),
		error=result.get("error"),
	)
	return result


def _read_weight_via_local_agent(machine, profile, manual_value=None) -> dict:
	from weighing_machine_integration.services import local_agent_client

	try:
		agent_result = local_agent_client.read_weight(machine.name, profile=_profile_to_dict(profile))
	except Exception as e:
		wlog.log_machine_event(machine.name, LOG_EVENT_ERROR, LOG_STATUS_FAILURE, error=str(e))
		return {"status": "Error", "error_message": str(e)}

	if not agent_result.get("success"):
		error = agent_result.get("error") or "Local Agent read failed"
		wlog.log_machine_event(machine.name, LOG_EVENT_ERROR, LOG_STATUS_FAILURE, error=error)
		return {"status": "Error", "error_message": error}

	wlog.log_machine_event(machine.name, LOG_EVENT_READ, LOG_STATUS_SUCCESS,
							raw_response=agent_result.get("raw_response"))

	stable = agent_result.get("stable")
	status = "Success"
	if machine.require_stable_weight and stable is False:
		status = "Unstable"

	return {
		"status": status,
		"weight": agent_result.get("weight"),
		"gross_weight": agent_result.get("gross_weight"),
		"tare_weight": agent_result.get("tare_weight"),
		"net_weight": agent_result.get("net_weight"),
		"unit": agent_result.get("unit") or machine.default_uom or profile.get("default_uom"),
		"stable": stable,
		"raw_response": agent_result.get("raw_response"),
		"error_message": None,
		"machine_profile": profile.name,
	}


def read_weight(machine_name: str, manual_value=None) -> dict:
	"""Returns a dict: {status, weight, gross_weight, tare_weight,
	net_weight, unit, stable, raw_response, error_message}. Never raises -
	hardware/config failures are reported in the returned dict so a bad
	machine never crashes the calling document/page.
	"""
	try:
		machine, profile = get_machine_and_profile(machine_name)
	except MachineNotFound as e:
		return {"status": "Error", "error_message": str(e)}

	if machine.connection_mode == "Local Agent":
		return _read_weight_via_local_agent(machine, profile, manual_value)

	kwargs = {}
	if profile.connection_type == "Manual":
		kwargs = {"manual_value": manual_value}

	try:
		driver = create_driver(profile, **kwargs)
	except DriverError as e:
		return {"status": "Error", "error_message": str(e)}

	try:
		driver.connect()
		wlog.log_machine_event(machine.name, LOG_EVENT_CONNECTION, LOG_STATUS_SUCCESS)
	except DriverError as e:
		wlog.log_machine_event(machine.name, LOG_EVENT_ERROR, LOG_STATUS_FAILURE, error=str(e))
		return {"status": "Error", "error_message": str(e)}

	try:
		if machine.require_stable_weight:
			result, stable = take_stable_reading(
				driver,
				minimum_stable_readings=machine.minimum_stable_readings,
				tolerance=profile.get("stability_tolerance") or 0.02,
			)
		else:
			result = driver.get_weight()
			stable = bool(result.stable) if result.stable is not None else None

		if result is None or result.resolve_weight() is None:
			wlog.log_machine_event(machine.name, LOG_EVENT_ERROR, LOG_STATUS_FAILURE,
									error="No weight could be read")
			return {"status": "Error", "error_message": "No weight could be read from the machine"}

		wlog.log_machine_event(machine.name, LOG_EVENT_READ, LOG_STATUS_SUCCESS,
								raw_response=result.raw_response)

		status = "Success"
		if machine.require_stable_weight and not stable:
			status = "Unstable"
		if kwargs.get("manual_value") is not None:
			status = "Manual"

		return {
			"status": status,
			"weight": result.resolve_weight(),
			"gross_weight": result.gross_weight,
			"tare_weight": result.tare_weight,
			"net_weight": result.net_weight,
			"unit": result.unit or machine.default_uom or profile.get("default_uom"),
			"stable": stable,
			"raw_response": result.raw_response,
			"error_message": None,
			"machine_profile": profile.name,
		}

	except DriverError as e:
		event = LOG_EVENT_TIMEOUT if "timed out" in str(e).lower() or "timeout" in str(e).lower() else LOG_EVENT_ERROR
		wlog.log_machine_event(machine.name, event, LOG_STATUS_FAILURE, error=str(e))
		return {"status": "Error", "error_message": str(e)}
	except Exception as e:
		frappe.log_error(title="weighing_machine_integration: unexpected read_weight failure",
						  message=frappe.get_traceback())
		wlog.log_machine_event(machine.name, LOG_EVENT_ERROR, LOG_STATUS_FAILURE, error=str(e))
		return {"status": "Error", "error_message": f"Unexpected error: {e}"}
	finally:
		try:
			driver.disconnect()
			wlog.log_machine_event(machine.name, LOG_EVENT_DISCONNECTION, LOG_STATUS_SUCCESS)
		except Exception:
			pass


def send_zero_or_tare(machine_name: str, action: str) -> dict:
	"""action: 'zero' or 'tare'."""
	try:
		machine, profile = get_machine_and_profile(machine_name)

		if machine.connection_mode == "Local Agent":
			from weighing_machine_integration.services import local_agent_client
			agent_fn = local_agent_client.zero if action == "zero" else local_agent_client.tare
			result = agent_fn(machine.name, profile=_profile_to_dict(profile))
			if result.get("success"):
				wlog.log_machine_event(machine.name, LOG_EVENT_READ, LOG_STATUS_SUCCESS, message=f"{action} command sent")
			return result

		driver = create_driver(profile)
		driver.connect()
		try:
			getattr(driver, action)()
			wlog.log_machine_event(machine.name, LOG_EVENT_READ, LOG_STATUS_SUCCESS, message=f"{action} command sent")
			return {"success": True}
		finally:
			driver.disconnect()
	except (MachineNotFound, DriverError) as e:
		return {"success": False, "error": str(e)}
