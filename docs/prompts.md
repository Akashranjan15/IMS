# Dev Notes

started with the debounce engine first since that felt like the hardest part. took a few tries to get the asyncio locking right.

used State pattern for workflow — seemed cleaner than a big if/else.

docker compose was straightforward. influxdb setup was annoying because of the init env vars.

frontend is basic react, no fancy libraries. gets the job done.

## useful prompts i found

### for triaging new incidents

Summarize incident {{incident_id}} for an on-call engineer.
Include severity, component, current status, first observed time, signal count,
known error codes, and the safest next diagnostic step.

### for reviewing RCA before closing

Review this RCA for completeness.
Check whether the root cause category is specific, the fix describes a concrete
change, and the prevention steps reduce recurrence rather than only detection.

### for stakeholder updates

Write a concise incident update with impact, current mitigation, ETA if known,
and the next update time. Avoid speculation.

