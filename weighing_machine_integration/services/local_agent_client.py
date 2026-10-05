"""Thin HTTP client the ERPNext server uses to talk to a Local Agent
running on a user's PC, when a Weighing Machine's Connection Mode is
"Local Agent" rather than "Server".

The agent itself (local_agent/agent.py) is a completely separate,
lightweight process - this module is the only place the server-side app
knows how to reach it.
"""

from __future__ import annotations

import frappe
import requests

from weighing_machine_integration.drivers.base import DriverError


def _agent_config():
	settings = frappe.get_single("Weighing Settings")
	if not settings.enable_local_agent:
		raise DriverError("Local Agent is not enabled in Weighing Settings")
	if not settings.local_agent_url:
		raise DriverError("Local Agent URL is not configured in Weighing Settings")
	return settings.local_agent_url.rstrip("/"), settings.get_password("local_agent_token")


def _headers(token):
	return {"Authorization": f"Bearer {token}"} if token else {}


def _call(method, path, machine_name=None, timeout=10, **kwargs):
	base_url, token = _agent_config()
	try:
		response = requests.request(
			method, f"{base_url}{path}",
			headers=_headers(token),
			json={"machine": machine_name, **kwargs} if machine_name else kwargs,
			timeout=timeout,
		)
	except requests.exceptions.Timeout:
		raise DriverError("Local Agent did not respond in time")
	except requests.exceptions.ConnectionError:
		raise DriverError("Could not reach the Local Agent - is it running?")
	except requests.exceptions.RequestException as e:
		raise DriverError(f"Local Agent request failed: {e}")

	if response.status_code == 401:
		raise DriverError("Local Agent rejected the configured token")
	if response.status_code >= 400:
		raise DriverError(f"Local Agent returned {response.status_code}: {response.text[:200]}")

	try:
		return response.json()
	except ValueError:
		raise DriverError("Local Agent returned a non-JSON response")


def health():
	return _call("GET", "/health")


def read_weight(machine_name: str, profile: dict = None):
	return _call("POST", "/read-weight", machine_name=machine_name, profile=profile)


def test_connection(machine_name: str, profile: dict = None):
	return _call("POST", "/test", machine_name=machine_name, profile=profile)


def zero(machine_name: str, profile: dict = None):
	return _call("POST", "/zero", machine_name=machine_name, profile=profile)


def tare(machine_name: str, profile: dict = None):
	return _call("POST", "/tare", machine_name=machine_name, profile=profile)
