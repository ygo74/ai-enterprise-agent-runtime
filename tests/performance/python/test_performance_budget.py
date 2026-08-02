import json
from pathlib import Path


def test_performance_budget_threshold_file() -> None:
    f = Path("tests/performance/baselines/performance_thresholds.json")
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["normalization_dispatch_p95_ms"] > 0
    assert data["auth_dispatch_pipeline_p95_ms"] > 0
    assert data["first_stream_event_p95_ms"] > 0
