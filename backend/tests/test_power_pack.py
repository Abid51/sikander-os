"""Smoke tests for observability, metrics, auth helpers (run: python tests/test_power_pack.py)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_metrics_inc_and_snapshot():
    from app.core import metrics
    metrics.reset()
    metrics.inc("t", 2)
    metrics.inc("t", 1)
    assert metrics.snapshot()["t"] == 3


def test_api_auth_disabled_by_default():
    from app.core import api_auth
    assert api_auth.is_auth_enabled() is False


def test_path_exempt():
    from app.core import api_auth
    assert api_auth.path_is_exempt("/docs", ("/docs", "/openapi.json"))
    assert not api_auth.path_is_exempt("/danger", ("/docs",))


def test_job_queue_module_loads():
    from app.core import job_queue
    assert job_queue.queue_depth() >= 0


if __name__ == "__main__":
    test_metrics_inc_and_snapshot()
    test_api_auth_disabled_by_default()
    test_path_exempt()
    test_job_queue_module_loads()
    print("power_pack: ok")
