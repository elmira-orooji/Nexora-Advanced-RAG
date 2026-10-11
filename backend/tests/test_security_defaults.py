from types import SimpleNamespace

from app.core.rate_limit import _get_client_ip
from app.services.operations.security_audit import audit_security_event


def test_untrusted_client_cannot_spoof_forwarded_ip():
    request = SimpleNamespace(headers={"x-forwarded-for": "203.0.113.44"}, client=SimpleNamespace(host="198.51.100.2"))

    assert _get_client_ip(request) == "198.51.100.2"


def test_security_audit_does_not_log_raw_ip(caplog):
    with caplog.at_level("WARNING"):
        audit_security_event("login", "denied", client_ip="203.0.113.44", reason="invalid_credentials")

    assert "203.0.113.44" not in caplog.text
    assert "Security audit event" in caplog.text
