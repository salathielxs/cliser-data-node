from node import health


def test_registry_database_failure_is_detected(monkeypatch):
    def failing_connect():
        raise RuntimeError("SIMULATED_DATABASE_FAILURE")

    monkeypatch.setattr(
        health,
        "connect",
        failing_connect,
    )

    result = health.check_registry()

    assert result["status"] == "ERROR"
    assert "SIMULATED_DATABASE_FAILURE" in result["detail"]


def test_registry_database_failure_does_not_report_ok(monkeypatch):
    def failing_connect():
        raise RuntimeError("DATABASE_UNAVAILABLE")

    monkeypatch.setattr(
        health,
        "connect",
        failing_connect,
    )

    result = health.check_registry()

    assert result["status"] != "OK"
    assert result["status"] == "ERROR"
