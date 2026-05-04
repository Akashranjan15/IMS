from prometheus_client import Counter, Gauge, Histogram

SIGNALS_ACCEPTED = Counter("ims_signals_accepted_total", "Signals accepted into the ingest queue", ["severity", "component_type"])
SIGNALS_REJECTED = Counter("ims_signals_rejected_total", "Signals rejected by the ingest API", ["reason"])
INCIDENTS_CREATED = Counter("ims_incidents_created_total", "Incidents created by the debounce engine", ["severity", "component_type"])
STATE_TRANSITIONS = Counter("ims_state_transitions_total", "Incident state transitions", ["from_status", "to_status"])
DB_WRITE_FAILURES = Counter("ims_db_write_failures_total", "Database write failures after retries", ["db"])
INGEST_QUEUE_DEPTH = Gauge("ims_ingest_queue_depth", "Current ingest queue depth")
API_LATENCY = Histogram("ims_api_latency_seconds", "API request latency", ["path", "method"])

