"""Shared constants. Nothing machine/customer-specific lives here."""

CONNECTION_TYPES = ("Serial", "TCP/IP", "HTTP API", "Modbus TCP", "Manual")

RESPONSE_FORMATS = ("Plain Numeric", "Regex", "JSON Path", "Delimited Gross/Tare/Net")

WEIGHT_UNITS = ("KG", "G", "LB", "TON")

READING_STATUS_SUCCESS = "Success"
READING_STATUS_UNSTABLE = "Unstable"
READING_STATUS_ERROR = "Error"
READING_STATUS_MANUAL = "Manual"

LOG_EVENT_CONNECTION = "Connection"
LOG_EVENT_DISCONNECTION = "Disconnection"
LOG_EVENT_READ = "Read"
LOG_EVENT_ERROR = "Error"
LOG_EVENT_TIMEOUT = "Timeout"
LOG_EVENT_RECONNECT = "Reconnect"

LOG_STATUS_SUCCESS = "Success"
LOG_STATUS_FAILURE = "Failure"

# Fields whose values must never be written to a log/error message.
SENSITIVE_FIELDS = ("http_password", "http_token", "local_agent_token", "password", "token")
