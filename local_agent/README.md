# Weighing Machine Integration - Local Agent

Runs on the Windows (or Linux/Mac) PC that a weighing machine is
physically connected to, when ERPNext can't reach that hardware directly
(the machine is on COM3 of someone's desktop, not on the ERPNext server).

ERPNext talks to this agent over HTTP; this agent talks to the actual
hardware (serial port, local TCP device, local HTTP device). It does not
depend on Frappe/ERPNext being installed - just Python + the packages in
`requirements.txt`.

## Install

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
```

## Configure

```bash
copy config.example.json config.json   # Windows
# cp config.example.json config.json   # Linux/Mac
```

Edit `config.json`:
- `port` - whatever port you want the agent to listen on.
- `token` - a long random string. Set the *same* value as the Weighing
  Settings > Local Agent Token in ERPNext. Requests without a matching
  `Authorization: Bearer <token>` header are rejected.
- `machines` - optional. By default ERPNext sends the full Weighing
  Machine Profile configuration with every request, so you don't need to
  duplicate it here. Only fill this in if you want to test the agent
  without ERPNext running (see below).

## Run

```bash
python agent.py --config config.json
```

Then in ERPNext:
- Weighing Settings: check "Enable Local Agent", set "Local Agent URL" to
  `http://<this-pc>:<port>` and "Local Agent Token" to the same token.
- Weighing Machine: set Connection Mode = "Local Agent".

## Run as a Windows service (optional)

The simplest approach is [NSSM](https://nssm.cc/): `nssm install WeighingAgent "C:\path\to\venv\Scripts\python.exe" "C:\path\to\agent.py --config C:\path\to\config.json"`.

## Test without any hardware

Run the simulator in one terminal:

```bash
python simulator.py --mode tcp --port 9000 --format plain
```

Then create a Weighing Machine Profile in ERPNext with:
- Connection Type: `TCP/IP`
- Host: the simulator machine's IP, Port: `9000`
- Response Format: `Plain Numeric`

Click "Test Connection" on the Weighing Machine - you should see a
fluctuating weight that settles after a few reads, exactly like a real
scale. Use `--format delimited` or `--format json` to test the other
response-format parsers (configure the matching Response Format /
regexes / JSON paths on the Profile).

## Endpoints

| Method | Path          | Body                                   |
|--------|---------------|-----------------------------------------|
| GET    | `/health`     | -                                        |
| GET    | `/machines`   | -                                        |
| POST   | `/connect`    | `{"machine": "...", "profile": {...}}`   |
| POST   | `/disconnect` | `{"machine": "..."}`                     |
| POST   | `/read-weight`| `{"machine": "...", "profile": {...}}`   |
| POST   | `/test`       | `{"machine": "...", "profile": {...}}`   |
| POST   | `/zero`       | `{"machine": "...", "profile": {...}}`   |
| POST   | `/tare`       | `{"machine": "...", "profile": {...}}`   |

`profile` is the same field shape as a Weighing Machine Profile document
(connection_type, serial_port, baud_rate, response_format, weight_regex,
...). ERPNext supplies it automatically on every call.

## Security notes

- Always set a `token` in production - an agent with no token accepts
  requests from anyone who can reach its port.
- Run this on a trusted local network, or put it behind a VPN/reverse
  proxy with TLS if ERPNext needs to reach it over the internet; the
  agent itself serves plain HTTP.
- The agent never logs passwords/tokens.
