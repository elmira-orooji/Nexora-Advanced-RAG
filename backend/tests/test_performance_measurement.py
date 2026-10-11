from sqlalchemy import create_engine, text

from app.services.operations.performance_measurement import (
    begin_request_measurement,
    finish_request_measurement,
    process_memory_bytes,
    register_sqlalchemy_query_metrics,
)


def test_request_measurement_counts_database_queries_and_timing():
    register_sqlalchemy_query_metrics()
    engine = create_engine("sqlite://")
    token = begin_request_measurement("/api/v1/test")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        measurement = finish_request_measurement(token, 0.01)
        engine.dispose()

    assert measurement is not None
    assert measurement.query_count == 1
    assert measurement.query_duration_seconds >= 0


def test_process_memory_measurement_is_non_negative():
    assert process_memory_bytes() >= 0
