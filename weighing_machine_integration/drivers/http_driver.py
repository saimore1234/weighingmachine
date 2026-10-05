"""HTTP/REST API driver for scales/indicators that expose a web API."""

from __future__ import annotations

import json

import requests

from weighing_machine_integration.drivers.base import BaseDriver, DriverError


class HTTPDriver(BaseDriver):
	"""HTTP is stateless, so connect()/disconnect() just validate config."""

	def connect(self) -> None:
		if not self.profile.get("http_url"):
			raise DriverError("No URL configured on this machine profile")
		self._connected = True

	def disconnect(self) -> None:
		self._connected = False

	def _headers(self) -> dict:
		headers = {}
		raw_headers = self.profile.get("http_headers")
		if raw_headers:
			try:
				headers.update(json.loads(raw_headers))
			except json.JSONDecodeError:
				raise DriverError("Headers field is not valid JSON")

		auth_type = self.profile.get("http_auth_type") or "None"
		if auth_type == "Bearer Token":
			token = self.profile.get("http_token")
			if token:
				headers["Authorization"] = f"Bearer {token}"
		elif auth_type == "API Key Header":
			token = self.profile.get("http_token")
			if token:
				headers["X-API-Key"] = token
		return headers

	def _auth(self):
		if (self.profile.get("http_auth_type") or "None") == "Basic":
			return (self.profile.get("http_username") or "", self.profile.get("http_password") or "")
		return None

	def read_raw(self) -> str:
		if not self._connected:
			raise DriverError("Not connected (call connect() first)")

		url = self.profile.get("http_url")
		method = (self.profile.get("http_method") or "GET").upper()
		timeout = float(self.profile.get("http_timeout") or 5)
		body = self.profile.get("http_request_body")
		json_body = None
		if body:
			try:
				json_body = json.loads(body)
			except json.JSONDecodeError:
				raise DriverError("Request Body is not valid JSON")

		try:
			response = requests.request(
				method=method,
				url=url,
				headers=self._headers(),
				auth=self._auth(),
				json=json_body,
				timeout=timeout,
			)
		except requests.exceptions.Timeout:
			raise DriverError(f"HTTP request to {url} timed out")
		except requests.exceptions.ConnectionError as e:
			raise DriverError(f"Could not connect to {url}: {e}")
		except requests.exceptions.RequestException as e:
			raise DriverError(f"HTTP request failed: {e}")

		if response.status_code in (401, 403):
			raise DriverError(f"HTTP authentication failed ({response.status_code})")
		if response.status_code >= 400:
			raise DriverError(f"HTTP request returned {response.status_code}: {response.text[:200]}")

		return response.text

	def send_command(self, command: str) -> None:
		# HTTP machines don't take a free-form wire command; a "command" here
		# is just another read with a different configured URL/body, which
		# is outside this generic driver's scope. No-op by design.
		return
