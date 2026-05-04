from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from models.postgres_models import RCARequest


def valid_payload() -> dict:
    start = datetime.now(timezone.utc) - timedelta(minutes=30)
    return {
        "incident_start": start,
        "incident_end": start + timedelta(minutes=20),
        "root_cause_category": "INFRA",
        "fix_applied": "Restarted the failed primary database node.",
        "prevention_steps": "Added automated failover validation and alerts.",
    }


def test_rca_accepts_complete_payload():
    rca = RCARequest(**valid_payload())

    assert rca.root_cause_category == "INFRA"


def test_rca_rejects_short_fix_applied():
    payload = valid_payload()
    payload["fix_applied"] = "too short"

    with pytest.raises(ValidationError):
        RCARequest(**payload)


def test_rca_rejects_short_prevention_steps():
    payload = valid_payload()
    payload["prevention_steps"] = "too short"

    with pytest.raises(ValidationError):
        RCARequest(**payload)


def test_rca_rejects_end_before_start():
    payload = valid_payload()
    payload["incident_end"] = payload["incident_start"] - timedelta(minutes=1)

    with pytest.raises(ValidationError):
        RCARequest(**payload)

