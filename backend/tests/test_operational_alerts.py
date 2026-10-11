from unittest.mock import MagicMock, patch

from app.services.operations import operational_alerts


@patch.object(operational_alerts, "ALERT_RECIPIENTS", ("ops@example.com",))
@patch.object(operational_alerts, "SMTP_FROM_EMAIL", "alerts@example.com")
@patch.object(operational_alerts, "SMTP_HOST", "smtp.example.com")
def test_alert_is_persisted_when_email_is_configured():
    session = MagicMock()
    session.scalar.return_value = None
    context = MagicMock()
    context.__enter__.return_value = session
    with patch.object(operational_alerts, "SessionLocal", return_value=context):
        assert operational_alerts.queue_operational_alert("model-failure", "Model failed", "Check provider")
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_alert_is_not_persisted_without_smtp_configuration():
    with patch.object(operational_alerts, "SessionLocal") as sessions:
        assert not operational_alerts.queue_operational_alert("model-failure", "Model failed", "Check provider")
    sessions.assert_not_called()


def test_failed_delivery_is_scheduled_for_retry():
    alert = MagicMock(status="sending", attempts=1)
    session = MagicMock()
    session.get.return_value = alert
    context = MagicMock()
    context.__enter__.return_value = session
    with patch.object(operational_alerts, "SessionLocal", return_value=context):
        operational_alerts._mark_failed("alert-id", OSError("smtp unavailable"))
    assert alert.status == "retrying"
    assert alert.next_attempt_at is not None
    session.commit.assert_called_once()
