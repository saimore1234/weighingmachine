#!/usr/bin/env python3
"""
Weighing Machine Simulator.

Lets you test the ENTIRE integration (driver -> parser -> Weighing
Reading -> Field Mapping -> target document) without any physical
weighing hardware. Point a Weighing Machine Profile's Connection Type at
TCP/IP or HTTP API, host/port at this simulator, and it behaves like a
real scale.

Usage:
	python simulator.py --mode tcp  --port 9000 --format plain
	python simulator.py --mode tcp  --port 9000 --format delimited
	python simulator.py --mode http --port 9100 --format json

Formats:
	plain       -> "1250.50 kg\\r\\n"
	delimited   -> "GW=1250.50,TW=10.00,NW=1240.50\\r\\n"
	json        -> {"data": {"weight": 1250.50, "unit": "kg", "stable": true}}

Weight jitters around a base value and reports "stable" once it settles,
so stability-detection logic (Minimum Stable Readings) can be exercised
end to end as well as the single-shot case.
"""

from __future__ import annotations

import argparse
import json
import random
import socketserver
import threading
import time


class WeightState:
	"""Shared, thread-safe simulated weight that settles to a target."""

	def __init__(self, base=1250.0, jitter=3.0, settle_after=3):
		self._lock = threading.Lock()
		self._base = base
		self._jitter = jitter
		self._settle_after = settle_after
		self._reads_since_change = 0

	def next_reading(self):
		with self._lock:
			self._reads_since_change += 1
			stable = self._reads_since_change >= self._settle_after
			noise = 0 if stable else random.uniform(-self._jitter, self._jitter)
			weight = round(self._base + noise, 2)
			return weight, stable

	def bump(self):
		"""Simulate the load on the scale changing (new item placed)."""
		with self._lock:
			self._base = round(random.uniform(50, 5000), 2)
			self._reads_since_change = 0


def format_response(fmt, weight, stable):
	tare = 10.0
	gross = round(weight + tare, 2)
	if fmt == "plain":
		return f"{weight:010.2f}kg\r\n"
	if fmt == "delimited":
		return f"GW={gross:.2f},TW={tare:.2f},NW={weight:.2f}\r\n"
	if fmt == "json":
		return json.dumps({"data": {"weight": weight, "gross": gross, "tare": tare,
									 "unit": "kg", "stable": stable}})
	raise ValueError(f"Unknown format: {fmt}")


def run_tcp(host, port, fmt, state):
	class Handler(socketserver.BaseRequestHandler):
		def handle(self):
			print(f"[simulator] TCP client connected: {self.client_address}")
			try:
				# Real scales in "continuous/streaming" mode send a reading
				# the moment a client connects, without waiting to be asked -
				# that's the common case (no Read Command configured), so
				# send first rather than blocking on recv().
				self.request.settimeout(0.2)
				while True:
					weight, stable = state.next_reading()
					response = format_response(fmt, weight, stable)
					self.request.sendall(response.encode("ascii"))
					try:
						data = self.request.recv(1024)
						if data == b"":
							break  # client closed the connection
					except TimeoutError:
						pass
					time.sleep(0.3)
			except (ConnectionResetError, BrokenPipeError):
				pass
			print(f"[simulator] TCP client disconnected: {self.client_address}")

	class Server(socketserver.ThreadingTCPServer):
		allow_reuse_address = True

	with Server((host, port), Handler) as server:
		print(f"[simulator] TCP simulator listening on {host}:{port} (format={fmt})")
		server.serve_forever()


def run_http(host, port, fmt, state):
	from flask import Flask, Response

	app = Flask(__name__)

	@app.route("/scale", methods=["GET"])
	def scale():
		weight, stable = state.next_reading()
		response = format_response(fmt, weight, stable)
		mimetype = "application/json" if fmt == "json" else "text/plain"
		return Response(response, mimetype=mimetype)

	@app.route("/bump", methods=["POST"])
	def bump():
		state.bump()
		return {"ok": True}

	print(f"[simulator] HTTP simulator listening on {host}:{port} (format={fmt}) - GET /scale")
	app.run(host=host, port=port)


def main():
	parser = argparse.ArgumentParser(description="Weighing machine simulator (no hardware required)")
	parser.add_argument("--mode", choices=["tcp", "http"], default="tcp")
	parser.add_argument("--host", default="0.0.0.0")
	parser.add_argument("--port", type=int, default=9000)
	parser.add_argument("--format", choices=["plain", "delimited", "json"], default="plain")
	parser.add_argument("--base-weight", type=float, default=1250.0)
	args = parser.parse_args()

	state = WeightState(base=args.base_weight)

	if args.mode == "tcp":
		run_tcp(args.host, args.port, args.format, state)
	else:
		run_http(args.host, args.port, args.format, state)


if __name__ == "__main__":
	main()
