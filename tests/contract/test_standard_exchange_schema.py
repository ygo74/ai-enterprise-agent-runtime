import json
from pathlib import Path


def test_standard_exchange_schema_exists() -> None:
    schema = Path("specs/001-openai-endpoint-exposure/contracts/standard-exchange-v1.schema.json")
    assert schema.exists()
    json.loads(schema.read_text(encoding="utf-8"))
