
import json
from typing import Any

from bson import json_util


def serialize_bson(value: Any) -> Any:
    """Convert BSON-compatible values into JSON-compatible values."""
    return json.loads(json_util.dumps(value))
