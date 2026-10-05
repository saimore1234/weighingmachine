#!/usr/bin/env python3
"""
Weighing Machine Integration - Local Agent

A small, standalone Flask service that runs on the PC the weighing machine
is physically attached to, when a Weighing Machine in ERPNext is set to
Connection Mode = "Local Agent". ERPNext never talks to the hardware
directly in that mode - it talks to this agent over HTTP, and this agent
talks to the COM port / local TCP socket / local HTTP device.

Deliberately self-contained (no dependency on the Frappe framework, no
import of the weighing_machine_integration Python package) so it can be
installed on a bare Windows PC with nothing but Python + a handful of
pip packages - see requirements.txt.

Run:
	python agent.py --config config.json

Config:
	See config.example.json. Copy it to config.json and edit, or set
	AGENT_CONFIG=/path/to/config.json.

Endpoints:
	GET  /health
	GET  /machines
	POST /connect       {"machine": "...", "profile": {...}}
	POST /disconnect    {"machine": "..."}
	POST /read-weight   {"machine": "...", "profile": {...}}
	POST /test          {"machine": "...", "profile": {...}}
	POST /zero          {"machine": "...", "profile": {...}}
	POST /tare          {"machine": "...", "profile": {...}}

`profile` is optional on every POST - when ERPNext sends it inline (the
default), that configuration is used directly and nothing needs to be
duplicated into this agent's own config.json. When omitted, the agent
looks the machine name up in its local config.json "machines" section,
so the agent can also be run/tested fully standalone.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import time
from functools import wraps

from flask import Flask, jsonify, request

try:
	import serial as pyserial
except ImportError:
	pyserial = None

try:
	import requests
except ImportError:
	requests = None


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

DEFAULT_CONFIG = {"host": "0.0.0.0", "port": 8585, "token": "", "machines": {}}


def load_config(path):
	if not path or not os.path.exists(path):
		print(f"[agent] WARNING: config file {path!r} not found, using defaults (no machines, no auth).")
		return dict(DEFAULT_CONFIG)
	with open(path, "r", encoding="utf-8") as f:
		config = json.load(f)
	merged = dict(DEFAULT_CONFIG)
	merged.update(config)
	return merged


# ----------------------------------------------------------------------
# Parsing (mirrors weighing_machine_integration/parsers - kept small and
# self-contained on purpose, see module docstring)
# ----------------------------------------------------------------------

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_UNIT_RE = re.compile(r"[A-Za-z]+")


def _to_float(value, decimal_separator=".", thousands_separator=""):
	if value is None:
		return None
	text = str(value).strip()
	if not text:
		return None
	if thousands_separator:
		text = text.replace(thousands_separator, "")
	if decimal_separator and decimal_separator != ".":
		text = text.replace(decimal_separator, ".")
	try:
		return float(text)
	except ValueError:
		return None


def _resolve_json_path(data, path):
	if not path:
		return None
	current = data
	for name, index in re.findall(r"([^.\[\]]+)|\[(\d+)\]", path):
		try:
			current = current[name] if name else current[int(index)]
		except (KeyError, IndexError, TypeError):
			return None
	return current


def parse_response(raw, profile):
	fmt = (profile or {}).get("response_format") or "Plain Numeric"
	precision = (profile or {}).get("decimal_precision") or 2
	dec_sep = (profile or {}).get("decimal_separator") or "."
	thou_sep = (profile or {}).get("thousands_separator") or ""

	result = {"weight": None, "gross_weight": None, "tare_weight": None, "net_weight": None,
			  "unit": None, "stable": None, "raw_response": raw}

	if fmt == "JSON Path":
		data = json.loads(raw)

		def num(path):
			v = _resolve_json_path(data, (profile or {}).get(path))
			return round(_to_float(v, dec_sep, thou_sep), precision) if v is not None else None

		result["weight"] = num("weight_json_path")
		result["gross_weight"] = num("gross_json_path")
		result["tare_weight"] = num("tare_json_path")
		result["net_weight"] = num("net_json_path")
		unit = _resolve_json_path(data, (profile or {}).get("unit_json_path"))
		result["unit"] = str(unit).upper() if unit is not None else None
		stable_path = (profile or {}).get("stable_json_path")
		if stable_path:
			stable_raw = _resolve_json_path(data, stable_path)
			result["stable"] = bool(stable_raw) if stable_raw is not None else None

	elif fmt in ("Regex", "Delimited Gross/Tare/Net"):
		def extract(pattern):
			if not pattern:
				return None
			m = re.search(pattern, raw)
			if not m:
				return None
			return m.group(1) if m.groups() else m.group(0)

		def num(key):
			v = extract((profile or {}).get(key))
			return round(_to_float(v, dec_sep, thou_sep), precision) if v is not None else None

		result["weight"] = num("weight_regex")
		result["gross_weight"] = num("gross_weight_regex")
		result["tare_weight"] = num("tare_weight_regex")
		result["net_weight"] = num("net_weight_regex")
		unit = extract((profile or {}).get("unit_regex"))
		result["unit"] = unit.upper() if unit else None

	else:  # Plain Numeric
		m = _NUMBER_RE.search(raw)
		if not m:
			raise ValueError(f"No numeric weight found in response: {raw!r}")
		result["weight"] = round(_to_float(m.group(0), dec_sep, thou_sep), precision)
		unit_match = _UNIT_RE.search(raw[m.end():])
		result["unit"] = unit_match.group(0).upper() if unit_match else None

	if result["weight"] is None:
		result["weight"] = result["net_weight"] if result["net_weight"] is not None else result["gross_weight"]
	if result["weight"] is None and result["gross_weight"] is None:
		raise ValueError(f"Could not parse a weight from response: {raw!r}")

	return result


# ----------------------------------------------------------------------
# Minimal drivers (Serial / TCP / HTTP) - same shape as the server app's,
# intentionally duplicated for a dependency-free standalone agent.
# ----------------------------------------------------------------------

def _unescape(value):
	return value.encode("utf-8").decode("unicode_escape") if value else ""


class AgentDriverError(Exception):
	pass


def read_serial(profile):
	if pyserial is None:
		raise AgentDriverError("pyserial is not installed. Run: pip install pyserial")
	port = profile.get("serial_port")
	if not port:
		raise AgentDriverError("No serial_port configured")

	parity_map = {"None": "N", "Even": "E", "Odd": "O", "Mark": "M", "Space": "S"}
	conn = pyserial.Serial(
		port=port,
		baudrate=int(profile.get("baud_rate") or 9600),
		bytesize=int(profile.get("data_bits") or 8),
		parity=parity_map.get(profile.get("parity") or "None", "N"),
		stopbits=float(profile.get("stop_bits") or 1),
		timeout=float(profile.get("serial_read_timeout") or 2),
		write_timeout=float(profile.get("serial_write_timeout") or 2),
	)
	try:
		command = profile.get("read_command")
		encoding = profile.get("serial_encoding") or "ascii"
		if command:
			terminator = _unescape(profile.get("command_terminator") or "\r\n")
			conn.write((command + terminator).encode(encoding, errors="ignore"))

		terminator = _unescape(profile.get("serial_line_terminator") or "\r\n")
		raw_bytes = conn.read_until(terminator.encode(encoding, errors="ignore")) if terminator else conn.readline()
		if not raw_bytes:
			raise AgentDriverError("Timed out waiting for a response from the machine")
		return raw_bytes.decode(encoding, errors="replace").strip()
	finally:
		conn.close()


def read_tcp(profile):
	host, port = profile.get("tcp_host"), profile.get("tcp_port")
	if not host or not port:
		raise AgentDriverError("tcp_host/tcp_port not configured")

	timeout = float(profile.get("tcp_socket_timeout") or 5)
	encoding = profile.get("tcp_encoding") or "ascii"
	terminator = _unescape(profile.get("tcp_terminator") or "\r\n").encode(encoding, errors="ignore")

	try:
		sock = socket.create_connection((host, int(port)), timeout=timeout)
	except OSError as e:
		raise AgentDriverError(f"Could not connect to {host}:{port}: {e}")

	try:
		command = profile.get("read_command")
		if command:
			cmd_terminator = _unescape(profile.get("command_terminator") or "\r\n")
			sock.sendall((command + cmd_terminator).encode(encoding, errors="ignore"))

		buffer = b""
		sock.settimeout(timeout)
		while terminator not in buffer:
			chunk = sock.recv(1024)
			if not chunk:
				break
			buffer += chunk
		if not buffer:
			raise AgentDriverError("No data received from TCP machine")
		return buffer.decode(encoding, errors="replace").strip()
	except socket.timeout:
		raise AgentDriverError("Timed out waiting for a response from the TCP machine")
	finally:
		sock.close()


def read_http(profile):
	if requests is None:
		raise AgentDriverError("requests is not installed. Run: pip install requests")
	url = profile.get("http_url")
	if not url:
		raise AgentDriverError("http_url not configured")
	try:
		response = requests.request(
			method=(profile.get("http_method") or "GET").upper(),
			url=url,
			timeout=float(profile.get("http_timeout") or 5),
		)
		response.raise_for_status()
		return response.text
	except requests.exceptions.RequestException as e:
		raise AgentDriverError(f"HTTP request failed: {e}")


_READERS = {"Serial": read_serial, "TCP/IP": read_tcp, "HTTP API": read_http}


def send_command(profile, command_field):
	command = profile.get(command_field)
	if not command:
		raise AgentDriverError(f"No {command_field} configured")

	connection_type = profile.get("connection_type")
	encoding = profile.get("serial_encoding") or profile.get("tcp_encoding") or "ascii"
	terminator = _unescape(profile.get("command_terminator") or "\r\n")

	if connection_type == "Serial":
		if pyserial is None:
			raise AgentDriverError("pyserial is not installed")
		conn = pyserial.Serial(profile.get("serial_port"), int(profile.get("baud_rate") or 9600),
								timeout=float(profile.get("serial_write_timeout") or 2))
		try:
			conn.write((command + terminator).encode(encoding, errors="ignore"))
		finally:
			conn.close()
	elif connection_type == "TCP/IP":
		sock = socket.create_connection((profile.get("tcp_host"), int(profile.get("tcp_port"))),
										 timeout=float(profile.get("tcp_socket_timeout") or 5))
		try:
			sock.sendall((command + terminator).encode(encoding, errors="ignore"))
		finally:
			sock.close()
	else:
		raise AgentDriverError(f"Sending commands is not supported for {connection_type}")


# ----------------------------------------------------------------------
# Flask app
# ----------------------------------------------------------------------

def create_app(config):
	app = Flask(__name__)
	app.config["AGENT_CONFIG"] = config

	def require_auth(fn):
		@wraps(fn)
		def wrapper(*args, **kwargs):
			token = config.get("token")
			if token:
				header = request.headers.get("Authorization", "")
				if header != f"Bearer {token}":
					return jsonify({"success": False, "error": "Unauthorized"}), 401
			return fn(*args, **kwargs)
		return wrapper

	def resolve_profile(machine_name, inline_profile):
		if inline_profile:
			return inline_profile
		machines = app.config["AGENT_CONFIG"].get("machines", {})
		if machine_name in machines:
			return machines[machine_name]
		raise AgentDriverError(f"No profile supplied and {machine_name!r} is not in this agent's config.json")

	@app.route("/health", methods=["GET"])
	def health():
		return jsonify({"status": "ok", "time": time.time()})

	@app.route("/machines", methods=["GET"])
	@require_auth
	def machines():
		return jsonify({"machines": list(app.config["AGENT_CONFIG"].get("machines", {}).keys())})

	@app.route("/connect", methods=["POST"])
	@require_auth
	def connect():
		payload = request.get_json(force=True, silent=True) or {}
		try:
			profile = resolve_profile(payload.get("machine"), payload.get("profile"))
			reader = _READERS.get(profile.get("connection_type"))
			if not reader:
				raise AgentDriverError(f"Unsupported connection_type: {profile.get('connection_type')!r}")
			reader(profile)  # connect+read+close, see module docstring
			return jsonify({"success": True, "connected": True})
		except Exception as e:
			return jsonify({"success": False, "error": str(e)}), 200

	@app.route("/disconnect", methods=["POST"])
	@require_auth
	def disconnect():
		return jsonify({"success": True, "disconnected": True})

	@app.route("/read-weight", methods=["POST"])
	@require_auth
	def read_weight_route():
		payload = request.get_json(force=True, silent=True) or {}
		try:
			profile = resolve_profile(payload.get("machine"), payload.get("profile"))
			reader = _READERS.get(profile.get("connection_type"))
			if not reader:
				raise AgentDriverError(f"Unsupported connection_type: {profile.get('connection_type')!r}")
			raw = reader(profile)
			parsed = parse_response(raw, profile)
			return jsonify({"success": True, **parsed})
		except Exception as e:
			return jsonify({"success": False, "error": str(e)}), 200

	@app.route("/test", methods=["POST"])
	@require_auth
	def test():
		started = time.monotonic()
		payload = request.get_json(force=True, silent=True) or {}
		try:
			profile = resolve_profile(payload.get("machine"), payload.get("profile"))
			reader = _READERS.get(profile.get("connection_type"))
			if not reader:
				raise AgentDriverError(f"Unsupported connection_type: {profile.get('connection_type')!r}")
			raw = reader(profile)
			parsed = parse_response(raw, profile)
			return jsonify({"success": True, "elapsed_seconds": round(time.monotonic() - started, 3), **parsed})
		except Exception as e:
			return jsonify({"success": False, "error": str(e),
							 "elapsed_seconds": round(time.monotonic() - started, 3)}), 200

	@app.route("/zero", methods=["POST"])
	@require_auth
	def zero():
		payload = request.get_json(force=True, silent=True) or {}
		try:
			profile = resolve_profile(payload.get("machine"), payload.get("profile"))
			send_command(profile, "zero_command")
			return jsonify({"success": True})
		except Exception as e:
			return jsonify({"success": False, "error": str(e)}), 200

	@app.route("/tare", methods=["POST"])
	@require_auth
	def tare():
		payload = request.get_json(force=True, silent=True) or {}
		try:
			profile = resolve_profile(payload.get("machine"), payload.get("profile"))
			send_command(profile, "tare_command")
			return jsonify({"success": True})
		except Exception as e:
			return jsonify({"success": False, "error": str(e)}), 200

	return app


def main():
	parser = argparse.ArgumentParser(description="Weighing Machine Integration - Local Agent")
	parser.add_argument("--config", default=os.environ.get("AGENT_CONFIG", "config.json"))
	args = parser.parse_args()

	config = load_config(args.config)
	app = create_app(config)
	print(f"[agent] Listening on {config['host']}:{config['port']} (auth {'ON' if config.get('token') else 'OFF'})")
	app.run(host=config["host"], port=int(config["port"]))


if __name__ == "__main__":
	main()
